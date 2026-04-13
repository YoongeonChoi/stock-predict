from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.database import db
from app.data import cache, yfinance_client
from app.scoring.selection import regime_alignment_score, score_selection_candidate
from app.services import market_service, portfolio_service
from app.services.portfolio_optimizer import attach_candidate_return_series
from app.utils.async_tools import gather_limited
from app.utils.market_calendar import trading_days_forward

COUNTRIES = ["KR"]


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _country_target_dates(reference_date: str) -> list[dict]:
    target_dates: list[dict] = []
    for country_code in COUNTRIES:
        try:
            target_days = trading_days_forward(country_code, reference_date, 20)
            target_date = target_days[-1].isoformat() if target_days else reference_date
        except Exception:
            target_date = reference_date
        target_dates.append(
            {
                "country_code": country_code,
                "target_date": target_date,
            }
        )
    return target_dates


def _risk_budget(market_views: list[dict], aggregate_up_probability: float) -> dict:
    risk_on = sum(1 for item in market_views if item.get("stance") == "risk_on")
    risk_off = sum(1 for item in market_views if item.get("stance") == "risk_off")
    cash_buffer = 14.0 + risk_off * 4.0 - risk_on * 2.0
    if aggregate_up_probability >= 58.0:
        cash_buffer -= 2.0
    elif aggregate_up_probability <= 49.0:
        cash_buffer += 3.0

    cash_buffer = round(_clip(cash_buffer, 8.0, 28.0), 2)
    recommended_equity_pct = round(100.0 - cash_buffer, 2)
    target_position_count = 5 if cash_buffer >= 24.0 else 6 if cash_buffer >= 18.0 else 7
    max_single_weight_pct = 13.0 if cash_buffer >= 22.0 else 14.5 if cash_buffer >= 16.0 else 16.0
    max_country_weight_pct = 36.0 if cash_buffer >= 22.0 else 40.0 if cash_buffer >= 16.0 else 44.0
    max_sector_weight_pct = 23.0 if cash_buffer >= 22.0 else 26.0 if cash_buffer >= 16.0 else 30.0

    style = "balanced"
    style_label = "균형형"
    if cash_buffer >= 22.0:
        style = "defensive"
        style_label = "방어형"
    elif cash_buffer <= 10.0:
        style = "offensive"
        style_label = "공격형"

    return {
        "style": style,
        "style_label": style_label,
        "recommended_equity_pct": recommended_equity_pct,
        "cash_buffer_pct": cash_buffer,
        "target_position_count": target_position_count,
        "max_single_weight_pct": max_single_weight_pct,
        "max_country_weight_pct": max_country_weight_pct,
        "max_sector_weight_pct": max_sector_weight_pct,
    }


def _candidate_score(opportunity: dict, market_view: dict) -> tuple[float, bool]:
    execution_bias = opportunity.get("execution_bias") or "stay_selective"
    action = opportunity.get("action") or "wait_pullback"
    expected_return_pct = float(opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0)
    expected_excess_return_pct = float(opportunity.get("expected_excess_return_pct_20d") or 0.0)
    forecast_volatility_pct = float(opportunity.get("forecast_volatility_pct_20d") or 0.0)
    up_probability = float(opportunity.get("up_probability_20d") or opportunity.get("up_probability") or 50.0)
    flat_probability = float(opportunity.get("flat_probability_20d") or opportunity.get("base_probability") or 0.0)
    down_probability = float(opportunity.get("down_probability_20d") or opportunity.get("bear_probability") or max(100.0 - up_probability, 0.0))
    distribution_confidence = float(opportunity.get("distribution_confidence_20d") or opportunity.get("confidence") or 50.0)
    signal_profile = market_service.build_distributional_signal_profile(
        current_price=float(opportunity.get("current_price") or 0.0),
        bull_case_price=opportunity.get("price_q75_20d") or opportunity.get("bull_case_price"),
        base_case_price=opportunity.get("price_q50_20d") or opportunity.get("base_case_price"),
        bear_case_price=opportunity.get("price_q25_20d") or opportunity.get("bear_case_price"),
        bull_probability=up_probability,
        base_probability=flat_probability,
        bear_probability=down_probability,
        predicted_return_pct=expected_return_pct,
        up_probability=up_probability,
        confidence=distribution_confidence,
    )
    selection = score_selection_candidate(
        expected_excess_return_pct=expected_excess_return_pct,
        calibrated_confidence=distribution_confidence,
        probability_edge=float(signal_profile["probability_edge"]),
        tail_ratio=float(signal_profile["tail_ratio"]),
        regime_alignment=regime_alignment_score(
            regime_tailwind=opportunity.get("regime_tailwind"),
            market_stance=market_view.get("stance"),
        ),
        analog_support=opportunity.get("analog_support_20d"),
        data_quality_support=opportunity.get("data_quality_support_20d"),
        downside_pct=float(signal_profile["downside_pct"]),
        forecast_volatility_pct=forecast_volatility_pct,
        action=action,
        execution_bias=execution_bias,
        legacy_score=float(opportunity.get("opportunity_score") or 0.0),
    )
    return round(selection.score, 2), selection.confidence_floor_passed


def _market_view(response: dict) -> dict:
    regime = response.get("market_regime") or {}
    stance = regime.get("stance", "neutral")
    return {
        "country_code": response.get("country_code", "KR"),
        "label": regime.get("label", "Neutral"),
        "stance": stance,
        "conviction": float(regime.get("conviction") or 0.0),
        "actionable_count": int(response.get("actionable_count") or 0),
        "bullish_count": int(response.get("bullish_count") or 0),
        "summary": regime.get("summary", ""),
    }


def _select_positions(candidates: list[dict], budget: dict) -> list[dict]:
    target_count = int(budget["target_position_count"])
    max_country_names = 2 if target_count <= 5 else 3
    selected: list[dict] = []
    country_counts: dict[str, int] = defaultdict(int)
    sector_counts: dict[str, int] = defaultdict(int)

    for candidate in sorted(candidates, key=lambda item: item["selection_score"], reverse=True):
        if len(selected) >= target_count:
            break
        if not candidate.get("confidence_floor_passed", True):
            continue
        minimum_score = 54.0 if candidate.get("execution_bias") in {"reduce_risk", "capital_preservation"} else 58.0
        if candidate["selection_score"] < minimum_score:
            continue
        if country_counts[candidate["country_code"]] >= max_country_names:
            continue
        if sector_counts[candidate["sector"]] >= 2:
            continue

        selected.append(candidate)
        country_counts[candidate["country_code"]] += 1
        sector_counts[candidate["sector"]] += 1

    if len(selected) < min(4, target_count):
        for candidate in sorted(candidates, key=lambda item: item["selection_score"], reverse=True):
            if len(selected) >= min(4, target_count):
                break
            if candidate in selected or not candidate.get("confidence_floor_passed", True) or candidate["selection_score"] < 54.0:
                continue
            selected.append(candidate)

    return selected


def _find_closest_close(price_history: list[dict], target_date: str) -> float | None:
    if not price_history:
        return None
    exact = next((row for row in price_history if row.get("date") == target_date), None)
    if exact:
        return float(exact.get("close") or 0.0)

    later = [row for row in price_history if str(row.get("date")) >= target_date]
    if later:
        return float(later[0].get("close") or 0.0)

    earlier = [row for row in price_history if str(row.get("date")) <= target_date]
    if earlier:
        return float(earlier[-1].get("close") or 0.0)
    return None


def _build_history_entry(row: dict) -> dict:
    portfolio = row["portfolio"]
    evaluation = row.get("evaluation")
    positions = portfolio.get("positions", [])
    summary = portfolio.get("summary", {})
    return {
        "reference_date": row.get("reference_date"),
        "generated_at": portfolio.get("generated_at"),
        "predicted_portfolio_return_pct": round(float(summary.get("expected_return_pct_20d") or summary.get("predicted_portfolio_return_pct") or 0.0), 2),
        "expected_excess_return_pct_20d": round(float(summary.get("expected_excess_return_pct_20d") or 0.0), 2),
        "realized_portfolio_return_pct": round(float(evaluation.get("portfolio_return_pct") or 0.0), 2) if evaluation else None,
        "evaluated": evaluation is not None,
        "hit_rate": round(float(evaluation.get("win_rate") or 0.0), 2) if evaluation else None,
        "direction_accuracy": round(float(evaluation.get("direction_accuracy") or 0.0), 2) if evaluation else None,
        "selected_count": len(positions),
        "top_tickers": [item.get("ticker") for item in positions[:3]],
    }


async def _evaluate_pending_snapshots(reference_date_to: str):
    pending = await db.ideal_portfolio_pending(reference_date_to, limit=12)
    if not pending:
        return

    history_cache: dict[str, list[dict]] = {}
    for row in pending:
        portfolio = row["portfolio"]
        positions = portfolio.get("positions", [])
        evaluated_positions = []
        weighted_return_sum = 0.0
        hit_count = 0
        direction_hits = 0
        scenario_hits = 0

        for item in positions:
            ticker = item.get("ticker")
            target_date = item.get("target_date_20d") or item.get("target_date")
            if not ticker or not target_date or target_date > reference_date_to:
                continue

            price_history = history_cache.get(ticker)
            if price_history is None:
                price_history = await yfinance_client.get_price_history(ticker, period="3mo")
                history_cache[ticker] = price_history

            actual_close = _find_closest_close(price_history, target_date)
            reference_price = float(item.get("reference_price") or 0.0)
            if actual_close is None or reference_price <= 0:
                continue

            realized_return_pct = (actual_close / reference_price - 1.0) * 100.0
            weight = float(item.get("target_weight_pct") or 0.0)
            direction_hit = (
                (float(item.get("expected_return_pct_20d") or item.get("predicted_return_pct") or 0.0) >= 0 and realized_return_pct >= 0)
                or (float(item.get("expected_return_pct_20d") or item.get("predicted_return_pct") or 0.0) < 0 and realized_return_pct < 0)
            )
            within_scenario = (
                float(item.get("price_q25_20d") or item.get("bear_case_price") or actual_close)
                <= actual_close
                <= float(item.get("price_q75_20d") or item.get("bull_case_price") or actual_close)
            )

            weighted_return_sum += realized_return_pct * weight
            hit_count += 1 if realized_return_pct > 0 else 0
            direction_hits += 1 if direction_hit else 0
            scenario_hits += 1 if within_scenario else 0
            evaluated_positions.append(
                {
                    "ticker": ticker,
                    "target_date": target_date,
                    "actual_close": round(actual_close, 2),
                    "realized_return_pct": round(realized_return_pct, 2),
                    "direction_hit": direction_hit,
                    "within_scenario": within_scenario,
                }
            )

        if not evaluated_positions:
            continue

        count = len(evaluated_positions)
        evaluation = {
            "evaluated_at": datetime.now().isoformat(),
            "portfolio_return_pct": round(weighted_return_sum / 100.0, 2),
            "win_rate": round(hit_count / count * 100.0, 2),
            "direction_accuracy": round(direction_hits / count * 100.0, 2),
            "within_scenario_rate": round(scenario_hits / count * 100.0, 2),
            "positions": evaluated_positions,
        }
        await db.ideal_portfolio_set_evaluation(row["reference_date"], evaluation)


async def _build_snapshot(reference_date: str) -> dict:
    radar_responses = await gather_limited(
        COUNTRIES,
        lambda country_code: market_service.get_market_opportunities(country_code, limit=8),
        limit=3,
    )
    responses = [response for response in radar_responses if not isinstance(response, Exception)]
    market_views = [_market_view(response) for response in responses]
    aggregate_up_probability = (
        sum(float(response.get("bullish_count") or 0.0) / max(float(response.get("actionable_count") or 1.0), 1.0) * 100.0 for response in responses) / max(len(responses), 1)
        if responses else 50.0
    )
    budget = _risk_budget(market_views, aggregate_up_probability)

    view_lookup = {item["country_code"]: item for item in market_views}
    candidates: list[dict] = []
    for response in responses:
        country_code = response.get("country_code", "KR")
        market_view = view_lookup.get(country_code, {})
        for opportunity in response.get("opportunities", [])[:6]:
            selection_score, confidence_floor_passed = _candidate_score(opportunity, market_view)
            candidates.append(
                {
                    "key": f"{country_code}:{opportunity.get('ticker')}",
                    "ticker": opportunity.get("ticker"),
                    "name": opportunity.get("name"),
                    "country_code": country_code,
                    "sector": opportunity.get("sector", "Other"),
                    "reference_price": round(float(opportunity.get("current_price") or 0.0), 2),
                    "target_date": opportunity.get("target_date_20d") or opportunity.get("forecast_date"),
                    "target_horizon_days": int(opportunity.get("target_horizon_days") or 20),
                    "target_date_20d": opportunity.get("target_date_20d") or opportunity.get("forecast_date"),
                    "selection_score": selection_score,
                    "confidence_floor_passed": confidence_floor_passed,
                    "opportunity_score": round(float(opportunity.get("opportunity_score") or 0.0), 1),
                    "up_probability_20d": round(float(opportunity.get("up_probability_20d") or opportunity.get("up_probability") or 0.0), 1),
                    "flat_probability_20d": round(float(opportunity.get("flat_probability_20d") or opportunity.get("base_probability") or 0.0), 1),
                    "down_probability_20d": round(float(opportunity.get("down_probability_20d") or opportunity.get("bear_probability") or 0.0), 1),
                    "confidence": round(float(opportunity.get("distribution_confidence_20d") or opportunity.get("confidence") or 0.0), 1),
                    "distribution_confidence_20d": round(float(opportunity.get("distribution_confidence_20d") or opportunity.get("confidence") or 0.0), 1),
                    "raw_confidence_20d": opportunity.get("raw_confidence_20d"),
                    "calibrated_probability_20d": opportunity.get("calibrated_probability_20d"),
                    "probability_edge_20d": opportunity.get("probability_edge_20d"),
                    "analog_support_20d": opportunity.get("analog_support_20d"),
                    "regime_support_20d": opportunity.get("regime_support_20d"),
                    "agreement_support_20d": opportunity.get("agreement_support_20d"),
                    "data_quality_support_20d": opportunity.get("data_quality_support_20d"),
                    "volatility_ratio_20d": opportunity.get("volatility_ratio_20d"),
                    "confidence_calibrator_20d": opportunity.get("confidence_calibrator_20d"),
                    "expected_return_pct_20d": round(float(opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0), 2),
                    "expected_excess_return_pct_20d": round(float(opportunity.get("expected_excess_return_pct_20d") or 0.0), 2),
                    "median_return_pct_20d": round(float(opportunity.get("median_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0), 2),
                    "forecast_volatility_pct_20d": round(float(opportunity.get("forecast_volatility_pct_20d") or 0.0), 2),
                    "price_q25_20d": opportunity.get("price_q25_20d") or opportunity.get("bear_case_price"),
                    "price_q50_20d": opportunity.get("price_q50_20d") or opportunity.get("base_case_price"),
                    "price_q75_20d": opportunity.get("price_q75_20d") or opportunity.get("bull_case_price"),
                    "up_probability": round(float(opportunity.get("up_probability_20d") or opportunity.get("up_probability") or 0.0), 1),
                    "predicted_return_pct": round(float(opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0), 2),
                    "bull_case_price": opportunity.get("price_q75_20d") or opportunity.get("bull_case_price"),
                    "base_case_price": opportunity.get("price_q50_20d") or opportunity.get("base_case_price"),
                    "bear_case_price": opportunity.get("price_q25_20d") or opportunity.get("bear_case_price"),
                    "bull_probability": opportunity.get("up_probability_20d") or opportunity.get("bull_probability"),
                    "base_probability": opportunity.get("flat_probability_20d") or opportunity.get("base_probability"),
                    "bear_probability": opportunity.get("down_probability_20d") or opportunity.get("bear_probability"),
                    "setup_label": opportunity.get("setup_label"),
                    "action": opportunity.get("action"),
                    "execution_bias": opportunity.get("execution_bias"),
                    "execution_note": opportunity.get("execution_note"),
                    "entry_low": opportunity.get("entry_low"),
                    "entry_high": opportunity.get("entry_high"),
                    "stop_loss": opportunity.get("stop_loss"),
                    "take_profit_1": opportunity.get("take_profit_1"),
                    "take_profit_2": opportunity.get("take_profit_2"),
                    "risk_reward_estimate": opportunity.get("risk_reward_estimate"),
                    "thesis": list(opportunity.get("thesis") or []),
                    "risk_flags": list(opportunity.get("risk_flags") or []),
                    "market_stance": market_view.get("stance", "neutral"),
                }
            )

    selected = _select_positions(candidates, budget)
    selected = await attach_candidate_return_series(selected, limit=4)
    positions, optimization = portfolio_service._allocate_model_weights(selected, budget)
    budget["recommended_equity_pct"] = optimization.actual_equity_pct
    budget["cash_buffer_pct"] = round(100.0 - optimization.actual_equity_pct, 2)

    country_alloc: dict[str, float] = defaultdict(float)
    sector_alloc: dict[str, float] = defaultdict(float)
    for item in positions:
        country_alloc[item["country_code"]] += float(item["target_weight_pct"])
        sector_alloc[item["sector"]] += float(item["target_weight_pct"])

    playbook = [
        f"현재 추천안은 {budget['style_label']} 기준으로 주식 {budget['recommended_equity_pct']:.1f}% / 현금 {budget['cash_buffer_pct']:.1f}%를 유지합니다.",
        f"20거래일 기대수익률 {optimization.expected_return_pct_20d:+.2f}%와 기대초과수익률 {optimization.expected_excess_return_pct_20d:+.2f}%를 기준으로 비중을 최적화했습니다.",
        f"예상 변동성은 {optimization.forecast_volatility_pct_20d:.2f}%, 예상 회전율은 {optimization.turnover_pct:.2f}%입니다.",
    ]
    if any(item.get("market_stance") == "risk_off" for item in positions):
        playbook.append("리스크오프 시장 종목은 목표 비중을 넘겨서 추격하지 말고, 손절 라인을 더 엄격히 관리하는 편이 좋습니다.")
    if any((item.get("risk_flags") or []) for item in positions):
        playbook.append("리스크 플래그가 붙은 종목은 비중 상단보다는 하단에서 시작하는 게 안전합니다.")

    return {
        "reference_date": reference_date,
        "generated_at": datetime.now().isoformat(),
        "objective": "20거래일 분포 기대수익률과 기대초과수익률, EWMA+shrinkage 공분산, 회전율 패널티를 함께 반영해 이상적인 포지션 조합과 비중을 제안하는 일일 포트폴리오입니다.",
        "target_dates": _country_target_dates(reference_date),
        "risk_budget": budget,
        "market_view": market_views,
        "summary": {
            "selected_count": len(positions),
            "predicted_portfolio_return_pct": round(optimization.expected_return_pct_20d, 2),
            "expected_return_pct_20d": round(optimization.expected_return_pct_20d, 2),
            "expected_excess_return_pct_20d": round(optimization.expected_excess_return_pct_20d, 2),
            "forecast_volatility_pct_20d": round(optimization.forecast_volatility_pct_20d, 2),
            "portfolio_up_probability": round(optimization.up_probability_20d, 2),
            "portfolio_down_probability": round(optimization.down_probability_20d, 2),
            "turnover_pct": round(optimization.turnover_pct, 2),
        },
        "allocation": {
            "by_country": [{"name": key, "value": round(value, 2)} for key, value in sorted(country_alloc.items(), key=lambda item: item[1], reverse=True)],
            "by_sector": [{"name": key, "value": round(value, 2)} for key, value in sorted(sector_alloc.items(), key=lambda item: item[1], reverse=True)],
        },
        "positions": positions,
        "playbook": playbook[:4],
    }


async def get_daily_ideal_portfolio(force_refresh: bool = False, history_limit: int = 10) -> dict:
    reference_date = datetime.now().date().isoformat()
    cache_key = f"ideal_portfolio_feed:v2:{reference_date}:{history_limit}"

    await _evaluate_pending_snapshots(reference_date)
    if not force_refresh:
        cached = await cache.get(cache_key)
        if cached:
            return cached

    snapshot_row = None if force_refresh else await db.ideal_portfolio_get(reference_date)
    if snapshot_row is None:
        snapshot = await _build_snapshot(reference_date)
        await db.ideal_portfolio_upsert(reference_date, snapshot)
        snapshot_row = await db.ideal_portfolio_get(reference_date)

    history_rows = await db.ideal_portfolio_list(limit=history_limit)
    response = {
        **snapshot_row["portfolio"],
        "history": [_build_history_entry(row) for row in history_rows],
    }
    await cache.set(cache_key, response, 900)
    return response
