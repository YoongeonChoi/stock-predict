from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from datetime import datetime

from app.analysis.distributional_return_engine import build_distributional_forecast
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.stock_analyzer import _calc_technicals
from app.analysis.trade_planner import build_trade_plan
from app.analysis.valuation_blend import build_quick_buy_sell
from app.data import cache, ecos_client, kosis_client, yfinance_client
from app.data.supabase_client import supabase_client
from app.models.country import COUNTRY_REGISTRY
from app.models.stock import PricePoint
from app.scoring.selection import regime_alignment_score, score_selection_candidate
from app.services import market_service, ticker_resolver_service
from app.services.portfolio_optimizer import (
    attach_candidate_return_series,
    build_horizon_snapshot,
    optimize_portfolio_weights,
)
from app.utils.async_tools import gather_limited


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_country_code(country_code: str | None) -> str:
    return ticker_resolver_service.normalize_country_code(country_code)


def _normalize_kr_portfolio_ticker(raw_ticker: str) -> str:
    return ticker_resolver_service.resolve_ticker(raw_ticker, "KR")["ticker"]


def normalize_portfolio_ticker(ticker: str, country_code: str = "KR") -> str:
    resolution = ticker_resolver_service.resolve_ticker(ticker, country_code)
    return resolution["ticker"]


def validate_portfolio_holding_input(
    ticker: str,
    buy_price: float,
    quantity: float,
    buy_date: str,
    country_code: str = "KR",
) -> dict[str, str | float]:
    normalized_country = _normalize_country_code(country_code)
    if normalized_country not in COUNTRY_REGISTRY:
        raise ValueError("지원하지 않는 국가 코드입니다. 한국(KR)만 지원합니다.")

    resolution = ticker_resolver_service.resolve_ticker(ticker, normalized_country)
    normalized_ticker = resolution["ticker"]
    if not normalized_ticker:
        raise ValueError("티커를 입력해 주세요.")

    try:
        parsed_buy_price = float(buy_price)
    except (TypeError, ValueError) as exc:
        raise ValueError("매수가는 0보다 큰 숫자로 입력해 주세요.") from exc
    if parsed_buy_price <= 0:
        raise ValueError("매수가는 0보다 큰 숫자로 입력해 주세요.")

    try:
        parsed_quantity = float(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("수량은 0보다 큰 숫자로 입력해 주세요.") from exc
    if parsed_quantity <= 0:
        raise ValueError("수량은 0보다 큰 숫자로 입력해 주세요.")

    normalized_buy_date = str(buy_date or "").strip()[:10]
    try:
        datetime.fromisoformat(normalized_buy_date)
    except ValueError as exc:
        raise ValueError("매수일은 YYYY-MM-DD 형식으로 입력해 주세요.") from exc

    return {
        "ticker": normalized_ticker,
        "buy_price": parsed_buy_price,
        "quantity": parsed_quantity,
        "buy_date": normalized_buy_date,
        "country_code": resolution["country_code"],
    }


def validate_portfolio_profile_input(
    total_assets: float,
    cash_balance: float,
    monthly_budget: float,
) -> dict[str, float]:
    try:
        parsed_total_assets = float(total_assets)
        parsed_cash_balance = float(cash_balance)
        parsed_monthly_budget = float(monthly_budget)
    except (TypeError, ValueError) as exc:
        raise ValueError("총자산, 예수금, 월 추가 자금은 숫자로 입력해 주세요.") from exc

    if parsed_total_assets < 0:
        raise ValueError("총자산은 0 이상으로 입력해 주세요.")
    if parsed_cash_balance < 0:
        raise ValueError("예수금은 0 이상으로 입력해 주세요.")
    if parsed_monthly_budget < 0:
        raise ValueError("월 추가 자금은 0 이상으로 입력해 주세요.")

    return {
        "total_assets": parsed_total_assets,
        "cash_balance": parsed_cash_balance,
        "monthly_budget": parsed_monthly_budget,
    }


def _default_portfolio_profile() -> dict[str, float | None]:
    return {
        "total_assets": 0.0,
        "cash_balance": 0.0,
        "monthly_budget": 0.0,
        "updated_at": None,
    }


def _portfolio_cache_key(user_id: str) -> str:
    return f"portfolio_overview:v8:{user_id}"


async def invalidate_portfolio_cache(user_id: str | None = None) -> None:
    if user_id:
        await cache.invalidate(f"%:{user_id}")
    await cache.invalidate("portfolio_overview:%")


def _build_asset_summary(
    *,
    profile: dict,
    total_invested: float,
    total_current: float,
    total_pnl: float,
    holding_count: int,
) -> dict[str, float | int]:
    tracked_total_assets = float(profile.get("total_assets") or 0.0)
    cash_balance = float(profile.get("cash_balance") or 0.0)
    monthly_budget = float(profile.get("monthly_budget") or 0.0)

    total_assets = max(tracked_total_assets, total_current + cash_balance)
    other_assets = max(total_assets - total_current - cash_balance, 0.0)
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested else 0.0
    stock_ratio_pct = (total_current / total_assets * 100.0) if total_assets else 0.0
    cash_ratio_pct = (cash_balance / total_assets * 100.0) if total_assets else 0.0
    other_assets_ratio_pct = (other_assets / total_assets * 100.0) if total_assets else 0.0
    asset_gap = tracked_total_assets - (total_current + cash_balance)

    return {
        "total_invested": round(total_invested, 2),
        "total_current": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "holding_count": holding_count,
        "total_assets": round(total_assets, 2),
        "cash_balance": round(cash_balance, 2),
        "other_assets": round(other_assets, 2),
        "stock_ratio_pct": round(stock_ratio_pct, 2),
        "cash_ratio_pct": round(cash_ratio_pct, 2),
        "other_assets_ratio_pct": round(other_assets_ratio_pct, 2),
        "monthly_budget": round(monthly_budget, 2),
        "deployable_cash": round(cash_balance + monthly_budget, 2),
        "asset_gap": round(asset_gap, 2),
        "unrealized_pnl_pct_of_assets": round((total_pnl / total_assets * 100.0) if total_assets else 0.0, 2),
    }


def _daily_returns(price_history: list[dict]) -> list[tuple[str, float]]:
    returns: list[tuple[str, float]] = []
    for prev, curr in zip(price_history, price_history[1:]):
        prev_close = float(prev.get("close") or 0)
        curr_close = float(curr.get("close") or 0)
        if prev_close <= 0:
            continue
        returns.append((str(curr.get("date")), curr_close / prev_close - 1.0))
    return returns


def _annualized_volatility(price_history: list[dict]) -> float:
    returns = [value for _, value in _daily_returns(price_history)]
    if len(returns) < 5:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / max(len(returns) - 1, 1)
    return math.sqrt(variance) * math.sqrt(252) * 100.0


def _max_drawdown(price_history: list[dict]) -> float:
    peak = 0.0
    drawdown = 0.0
    for row in price_history:
        close = float(row.get("close") or 0)
        peak = max(peak, close)
        if peak > 0:
            drawdown = min(drawdown, close / peak - 1.0)
    return abs(drawdown) * 100.0


def _beta(price_history: list[dict], benchmark_history: list[dict]) -> float | None:
    stock_returns = dict(_daily_returns(price_history))
    benchmark_returns = dict(_daily_returns(benchmark_history))
    common_dates = sorted(set(stock_returns) & set(benchmark_returns))
    if len(common_dates) < 10:
        return None

    stock_series = [stock_returns[date] for date in common_dates]
    bench_series = [benchmark_returns[date] for date in common_dates]
    stock_mean = sum(stock_series) / len(stock_series)
    bench_mean = sum(bench_series) / len(bench_series)
    variance = sum((value - bench_mean) ** 2 for value in bench_series) / max(len(bench_series) - 1, 1)
    if variance <= 1e-12:
        return None
    covariance = sum(
        (stock_value - stock_mean) * (bench_value - bench_mean)
        for stock_value, bench_value in zip(stock_series, bench_series)
    ) / max(len(common_dates) - 1, 1)
    return covariance / variance


def _risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _scenario_snapshot(forecast) -> dict[str, float | None]:
    scenarios = {item.name: item for item in getattr(forecast, "scenarios", [])}
    bull = scenarios.get("Bull")
    base = scenarios.get("Base")
    bear = scenarios.get("Bear")
    return {
        "bull_case_price": bull.price if bull else None,
        "base_case_price": base.price if base else None,
        "bear_case_price": bear.price if bear else None,
        "bull_probability": bull.probability if bull else None,
        "base_probability": base.probability if base else None,
        "bear_probability": bear.probability if bear else None,
    }


def _execution_mix(holdings: list[dict]) -> list[dict]:
    ordering = [
        "press_long",
        "lean_long",
        "stay_selective",
        "reduce_risk",
        "capital_preservation",
    ]
    grouped: dict[str, dict] = {}
    for holding in holdings:
        bias = holding.get("execution_bias") or "stay_selective"
        bucket = grouped.setdefault(bias, {"bias": bias, "count": 0, "weight": 0.0})
        bucket["count"] += 1
        bucket["weight"] += float(holding.get("weight_pct") or 0.0)

    results = []
    for bias in ordering:
        if bias in grouped:
            item = grouped[bias]
            item["weight"] = round(item["weight"], 2)
            results.append(item)
    return results


def _action_queue(holdings: list[dict]) -> list[dict]:
    candidates: list[tuple[float, dict]] = []
    for holding in holdings:
        execution_bias = holding.get("execution_bias") or "stay_selective"
        action = holding.get("trade_action") or "wait_pullback"
        risk_score = float(holding.get("risk_score") or 0.0)
        conviction = float(holding.get("trade_conviction") or 0.0)
        predicted_return = abs(float(holding.get("predicted_return_pct") or 0.0))
        priority = predicted_return + conviction * 0.2
        if execution_bias == "capital_preservation":
            priority += 90.0 + risk_score
        elif execution_bias == "reduce_risk":
            priority += 70.0 + risk_score * 0.4
        elif action in {"accumulate", "breakout_watch"}:
            priority += 55.0
        elif execution_bias == "lean_long":
            priority += 36.0
        else:
            priority += 18.0

        reason = ""
        risk_flags = holding.get("risk_flags") or []
        thesis = holding.get("thesis") or []
        if risk_flags:
            reason = risk_flags[0]
        elif thesis:
            reason = thesis[0]
        elif holding.get("execution_note"):
            reason = holding["execution_note"]

        candidates.append(
            (
                priority,
                {
                    "ticker": holding.get("ticker"),
                    "name": holding.get("name"),
                    "action": action,
                    "execution_bias": execution_bias,
                    "weight_pct": round(float(holding.get("weight_pct") or 0.0), 2),
                    "reason": reason,
                },
            )
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in candidates[:4]]


def _regime_weight_summary(country_context: dict, country_weights: dict[str, float]) -> list[dict]:
    summary = []
    for country_code, weight in sorted(country_weights.items(), key=lambda item: item[1], reverse=True):
        regime = country_context.get(country_code, {}).get("market_regime")
        if not regime:
            continue
        summary.append(
            {
                "country_code": country_code,
                "weight": round(weight, 2),
                "label": regime.label,
                "stance": regime.stance,
                "conviction": regime.conviction,
            }
        )
    return summary


def _stress_scenarios(
    *,
    total_current: float,
    total_invested: float,
    portfolio_beta: float,
    avg_volatility_pct: float,
    projected_next_day_pct: float,
    concentration_penalty: float,
) -> list[dict]:
    if total_current <= 0:
        return []

    shock_multiplier = 1.0 + concentration_penalty * 0.8 + max(portfolio_beta - 1.0, 0) * 0.35
    scenarios = [
        {
            "name": "Model Base Case",
            "description": "Weighted next-session move implied by the live forecast stack.",
            "projected_portfolio_pct": round(projected_next_day_pct, 2),
            "projected_pnl": round(total_current * projected_next_day_pct / 100.0, 2),
        },
        {
            "name": "Risk-On Extension",
            "description": "Momentum continues and broad market beta helps cyclical names.",
            "projected_portfolio_pct": round(projected_next_day_pct + max(portfolio_beta, 0.6) * 0.9, 2),
            "projected_pnl": round(total_current * (projected_next_day_pct + max(portfolio_beta, 0.6) * 0.9) / 100.0, 2),
        },
        {
            "name": "Shock Day",
            "description": "Broad de-risking scenario using portfolio beta, realized volatility, and concentration.",
            "projected_portfolio_pct": round(-(max(avg_volatility_pct / 5.0, 1.8) * shock_multiplier), 2),
            "projected_pnl": round(total_current * (-(max(avg_volatility_pct / 5.0, 1.8) * shock_multiplier)) / 100.0, 2),
        },
    ]

    if total_invested > 0:
        scenarios.append(
            {
                "name": "Break-Even Drift",
                "description": "Move required from current mark to recover invested capital.",
                "projected_portfolio_pct": round((total_invested / total_current - 1.0) * 100.0, 2),
                "projected_pnl": round(total_invested - total_current, 2),
            }
        )

    return scenarios


def _portfolio_model_defaults(note: str) -> dict:
    return {
        "as_of": datetime.now().isoformat(),
        "objective": "20거래일 분포 기대수익률, 기대초과수익, EWMA+shrinkage 공분산, 회전율 패널티를 함께 반영한 모델 포트폴리오 제안입니다.",
        "risk_budget": {
            "style": "balanced",
            "style_label": "균형형",
            "recommended_equity_pct": 0.0,
            "cash_buffer_pct": 100.0,
            "target_position_count": 0,
            "max_single_weight_pct": 0.0,
            "max_country_weight_pct": 0.0,
            "max_sector_weight_pct": 0.0,
        },
        "summary": {
            "selected_count": 0,
            "new_position_count": 0,
            "trim_count": 0,
            "watchlist_focus_count": 0,
            "model_up_probability": 0.0,
            "model_predicted_return_pct": 0.0,
            "expected_return_pct_20d": 0.0,
            "expected_excess_return_pct_20d": 0.0,
            "forecast_volatility_pct_20d": 0.0,
            "up_probability_20d": 0.0,
            "down_probability_20d": 0.0,
            "turnover_pct": 0.0,
        },
        "allocation": {
            "by_country": [],
            "by_sector": [],
        },
        "recommended_holdings": [],
        "rebalance_actions": [],
        "candidate_pipeline": [],
        "notes": [note],
    }


def _model_budget(
    *,
    overall_label: str,
    portfolio_up_probability: float,
    risk_off_weight: float,
    downside_watch_weight: float,
) -> dict:
    cash_buffer = 10.0
    style = "offensive"
    style_label = "공격형"

    if overall_label == "aggressive":
        cash_buffer = 26.0
        style = "defensive"
        style_label = "방어형"
    elif overall_label == "elevated":
        cash_buffer = 20.0
        style = "defensive"
        style_label = "방어형"
    elif overall_label == "moderate":
        cash_buffer = 14.0
        style = "balanced"
        style_label = "균형형"

    if portfolio_up_probability <= 47.0:
        cash_buffer += 4.0
    elif portfolio_up_probability >= 57.0:
        cash_buffer -= 2.0

    if risk_off_weight >= 35.0:
        cash_buffer += 5.0
    if downside_watch_weight >= 40.0:
        cash_buffer += 4.0

    cash_buffer = round(_clip(cash_buffer, 6.0, 32.0), 2)
    recommended_equity_pct = round(100.0 - cash_buffer, 2)
    target_position_count = 5 if cash_buffer >= 24.0 else 6 if cash_buffer >= 18.0 else 7 if cash_buffer >= 12.0 else 8
    max_single_weight_pct = 13.0 if cash_buffer >= 24.0 else 14.5 if cash_buffer >= 18.0 else 16.0
    max_country_weight_pct = 42.0 if cash_buffer >= 24.0 else 46.0 if cash_buffer >= 18.0 else 52.0
    max_sector_weight_pct = 24.0 if cash_buffer >= 24.0 else 28.0 if cash_buffer >= 18.0 else 32.0

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


def _supplement_scan_countries(country_codes: list[str]) -> list[str]:
    ordered: list[str] = []
    for code in country_codes:
        if code in COUNTRY_REGISTRY and code not in ordered:
            ordered.append(code)

    for fallback in ["KR"]:
        if fallback not in ordered:
            ordered.append(fallback)
        if len(ordered) >= 2:
            break

    return ordered[:2]


def _candidate_action(
    *,
    current_weight_pct: float,
    target_weight_pct: float,
    execution_bias: str | None = None,
) -> str:
    if current_weight_pct <= 0.1 and target_weight_pct < 1.0 and execution_bias in {"reduce_risk", "capital_preservation"}:
        return "hold"
    delta = target_weight_pct - current_weight_pct
    if current_weight_pct > 0.0 and target_weight_pct < 1.0:
        return "exit"
    if current_weight_pct <= 0.1 and target_weight_pct >= 3.0:
        return "new"
    if delta >= 3.5:
        return "add"
    if delta <= -4.0:
        return "trim"
    return "hold"


def _priority_label(priority_score: float) -> str:
    if priority_score >= 18.0:
        return "high"
    if priority_score >= 10.0:
        return "medium"
    return "low"


def _distributional_view(payload: dict | None) -> dict[str, float | str | None]:
    data = payload or {}
    up_probability = float(data.get("up_probability_20d") or data.get("up_probability") or 50.0)
    down_probability = data.get("down_probability_20d")
    if down_probability is None:
        down_probability = data.get("bear_probability")
    down_probability = float(down_probability or max(100.0 - up_probability, 0.0))
    flat_probability = data.get("flat_probability_20d")
    if flat_probability is None:
        flat_probability = max(100.0 - up_probability - down_probability, 0.0)
    return {
        "target_date": data.get("target_date_20d") or data.get("forecast_date"),
        "expected_return_pct": float(data.get("expected_return_pct_20d") or data.get("predicted_return_pct") or 0.0),
        "expected_excess_return_pct": float(data.get("expected_excess_return_pct_20d") or 0.0),
        "median_return_pct": float(data.get("median_return_pct_20d") or data.get("predicted_return_pct") or 0.0),
        "forecast_volatility_pct": float(data.get("forecast_volatility_pct_20d") or data.get("realized_volatility_pct") or 0.0),
        "up_probability": up_probability,
        "flat_probability": float(flat_probability),
        "down_probability": down_probability,
        "confidence": float(data.get("distribution_confidence_20d") or data.get("confidence") or data.get("trade_conviction") or 50.0),
        "raw_confidence": data.get("raw_confidence_20d") or data.get("raw_confidence"),
        "calibrated_probability": data.get("calibrated_probability_20d") or data.get("calibrated_probability"),
        "probability_edge": data.get("probability_edge_20d") or data.get("probability_edge"),
        "analog_support": data.get("analog_support_20d") or data.get("analog_support"),
        "regime_support": data.get("regime_support_20d") or data.get("regime_support"),
        "agreement_support": data.get("agreement_support_20d") or data.get("agreement_support"),
        "data_quality_support": data.get("data_quality_support_20d") or data.get("data_quality_support"),
        "volatility_ratio": data.get("volatility_ratio_20d") or data.get("volatility_ratio"),
        "confidence_calibrator": data.get("confidence_calibrator_20d") or data.get("confidence_calibrator"),
        "bull_case_price": data.get("price_q75_20d") or data.get("bull_case_price"),
        "base_case_price": data.get("price_q50_20d") or data.get("base_case_price"),
        "bear_case_price": data.get("price_q25_20d") or data.get("bear_case_price"),
    }


def _holding_model_score(holding: dict, radar_match: dict | None = None) -> tuple[float, list[str]]:
    merged = {**(radar_match or {}), **holding}
    dist_view = _distributional_view(merged)
    trade_conviction = float(holding.get("trade_conviction") or 50.0)
    risk_score = float(holding.get("risk_score") or 50.0)
    execution_bias = holding.get("execution_bias") or (radar_match or {}).get("execution_bias") or "stay_selective"
    trade_action = holding.get("trade_action") or (radar_match or {}).get("action") or "wait_pullback"
    signal_profile = market_service.build_distributional_signal_profile(
        current_price=float(holding.get("current_price") or 0.0),
        bull_case_price=dist_view["bull_case_price"],
        base_case_price=dist_view["base_case_price"],
        bear_case_price=dist_view["bear_case_price"],
        bull_probability=dist_view["up_probability"],
        base_probability=dist_view["flat_probability"],
        bear_probability=dist_view["down_probability"],
        predicted_return_pct=float(dist_view["expected_return_pct"] or 0.0),
        up_probability=float(dist_view["up_probability"] or 50.0),
        confidence=float(dist_view["confidence"] or trade_conviction),
    )
    selection = score_selection_candidate(
        expected_excess_return_pct=float(dist_view["expected_excess_return_pct"] or 0.0),
        calibrated_confidence=float(dist_view["confidence"] or trade_conviction),
        probability_edge=float(signal_profile["probability_edge"]),
        tail_ratio=float(signal_profile["tail_ratio"]),
        regime_alignment=regime_alignment_score(
            regime_tailwind=(radar_match or {}).get("regime_tailwind"),
            market_stance=holding.get("market_regime_stance"),
        ),
        analog_support=dist_view["analog_support"],
        data_quality_support=dist_view["data_quality_support"],
        downside_pct=float(signal_profile["downside_pct"]),
        forecast_volatility_pct=float(dist_view["forecast_volatility_pct"] or 0.0),
        action=trade_action,
        execution_bias=execution_bias,
        legacy_score=float(radar_match.get("opportunity_score") or trade_conviction) if radar_match else trade_conviction,
    )
    score = selection.score

    notes = [
        f"20거래일 기대초과수익률 {float(dist_view['expected_excess_return_pct'] or 0.0):+.2f}%, 보정 confidence {float(dist_view['confidence'] or trade_conviction):.1f}점을 함께 반영했습니다.",
        f"상하방 확률 격차 {signal_profile['probability_edge']:+.1f}pt와 실행 바이어스 `{execution_bias}`를 tie-breaker까지 포함해 정렬했습니다.",
    ]
    if not selection.confidence_floor_passed:
        notes.append(f"보정 confidence가 {selection.confidence_floor:.0f}점 미만이라 가중치를 낮춰 평가했습니다.")
    risk_flags = holding.get("risk_flags") or []
    thesis = holding.get("thesis") or []
    if risk_flags:
        notes.append(risk_flags[0])
    elif thesis:
        notes.append(thesis[0])

    return round(_clip(score, 0.0, 100.0), 1), notes[:3]


def _radar_model_score(opportunity: dict, watchlist_keys: set[str]) -> tuple[float, list[str], str, bool]:
    watchlist_key = f"{opportunity.get('country_code', 'KR')}:{opportunity.get('ticker')}"
    is_watchlist = watchlist_key in watchlist_keys
    execution_bias = opportunity.get("execution_bias") or "stay_selective"
    action = opportunity.get("action") or "wait_pullback"
    dist_view = _distributional_view(opportunity)

    signal_profile = market_service.build_distributional_signal_profile(
        current_price=float(opportunity.get("current_price") or 0.0),
        bull_case_price=dist_view["bull_case_price"],
        base_case_price=dist_view["base_case_price"],
        bear_case_price=dist_view["bear_case_price"],
        bull_probability=dist_view["up_probability"],
        base_probability=dist_view["flat_probability"],
        bear_probability=dist_view["down_probability"],
        predicted_return_pct=float(dist_view["expected_return_pct"] or 0.0),
        up_probability=float(dist_view["up_probability"] or 50.0),
        confidence=float(dist_view["confidence"] or 50.0),
    )
    selection = score_selection_candidate(
        expected_excess_return_pct=float(dist_view["expected_excess_return_pct"] or 0.0),
        calibrated_confidence=float(dist_view["confidence"] or 50.0),
        probability_edge=float(signal_profile["probability_edge"]),
        tail_ratio=float(signal_profile["tail_ratio"]),
        regime_alignment=regime_alignment_score(
            regime_tailwind=opportunity.get("regime_tailwind"),
            market_stance=None,
        ),
        analog_support=dist_view["analog_support"],
        data_quality_support=dist_view["data_quality_support"],
        downside_pct=float(signal_profile["downside_pct"]),
        forecast_volatility_pct=float(dist_view["forecast_volatility_pct"] or 0.0),
        action=action,
        execution_bias=execution_bias,
        legacy_score=float(opportunity.get("opportunity_score") or 0.0),
    )
    score = selection.score + (3.0 if is_watchlist else 0.0)
    score = round(_clip(score, 0.0, 100.0), 1)

    notes = [
        f"20거래일 기대초과수익률 {float(dist_view['expected_excess_return_pct'] or 0.0):+.2f}%, 보정 confidence {float(dist_view['confidence'] or 50.0):.1f}점을 기준으로 신규 편입 후보를 정렬했습니다.",
        f"상하방 확률 격차 {signal_profile['probability_edge']:+.1f}pt와 액션 `{action}`을 tie-breaker로만 사용했습니다.",
    ]
    if is_watchlist:
        notes.append("워치리스트에 있던 종목이라 우선순위를 한 단계 높였습니다.")
    if not selection.confidence_floor_passed:
        notes.append(f"보정 confidence가 {selection.confidence_floor:.0f}점 미만이라 편입 점수를 제한했습니다.")
    risk_flags = opportunity.get("risk_flags") or []
    thesis = opportunity.get("thesis") or []
    if risk_flags:
        notes.append(risk_flags[0])
    elif thesis:
        notes.append(thesis[0])

    return score, notes[:3], "watchlist" if is_watchlist else "radar", selection.confidence_floor_passed


def _select_model_candidates(candidates: list[dict], target_count: int) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get("model_score", 0.0)
            + (3.0 if item.get("source") == "holding" else 0.0)
            + (2.0 if item.get("in_watchlist") else 0.0)
        ),
        reverse=True,
    )

    selected: list[dict] = []
    country_counts: dict[str, int] = defaultdict(int)
    sector_counts: dict[str, int] = defaultdict(int)
    seen_keys: set[str] = set()

    for candidate in ordered:
        if len(selected) >= target_count:
            break
        key = candidate["key"]
        if key in seen_keys:
            continue
        is_defensive = candidate.get("execution_bias") in {"reduce_risk", "capital_preservation"}
        if candidate.get("source") == "holding" and is_defensive:
            minimum_score = 40.0
        elif candidate.get("source") == "holding":
            minimum_score = 48.0
        else:
            minimum_score = 52.0 if is_defensive else 56.0
        if float(candidate.get("model_score") or 0.0) < minimum_score:
            continue
        if country_counts[candidate["country_code"]] >= 3:
            continue
        if sector_counts[candidate["sector"]] >= 2:
            continue

        selected.append(candidate)
        seen_keys.add(key)
        country_counts[candidate["country_code"]] += 1
        sector_counts[candidate["sector"]] += 1

    minimum_fill = min(target_count, max(4, min(len(ordered), 4)))
    if len(selected) < minimum_fill:
        for candidate in ordered:
            if len(selected) >= minimum_fill:
                break
            key = candidate["key"]
            if key in seen_keys or float(candidate.get("model_score") or 0.0) < 45.0:
                continue
            if country_counts[candidate["country_code"]] >= 4:
                continue
            selected.append(candidate)
            seen_keys.add(key)
            country_counts[candidate["country_code"]] += 1

    defensive_holding_candidates = [
        candidate
        for candidate in ordered
        if candidate.get("source") == "holding"
        and candidate.get("execution_bias") in {"reduce_risk", "capital_preservation"}
        and float(candidate.get("current_weight_pct") or 0.0) > 0.1
        and candidate["key"] not in seen_keys
    ]
    for candidate in defensive_holding_candidates[:2]:
        selected.append(candidate)
        seen_keys.add(candidate["key"])

    return selected


def _allocate_model_weights(selected: list[dict], budget: dict) -> tuple[list[dict], object]:
    if not selected:
        return [], optimize_portfolio_weights([], budget)

    optimized_candidates = [
        item for item in selected
        if item.get("execution_bias") not in {"reduce_risk", "capital_preservation"}
    ]
    optimization = optimize_portfolio_weights(optimized_candidates, budget)
    targets = optimization.target_weights

    rounded_selected: list[dict] = []
    for item in selected:
        dist_view = _distributional_view(item)
        current_weight_pct = round(float(item.get("current_weight_pct") or 0.0), 2)
        execution_bias = item.get("execution_bias")
        proposed_target_weight_pct = round(float(targets.get(item["key"], 0.0)), 2)
        if execution_bias in {"reduce_risk", "capital_preservation"}:
            target_weight_pct = round(min(proposed_target_weight_pct, current_weight_pct), 2) if current_weight_pct > 0.1 else 0.0
        else:
            target_weight_pct = proposed_target_weight_pct
        delta_weight_pct = round(target_weight_pct - current_weight_pct, 2)
        action = _candidate_action(
            current_weight_pct=current_weight_pct,
            target_weight_pct=target_weight_pct,
            execution_bias=execution_bias,
        )
        priority_score = (
            abs(delta_weight_pct) * 2.0
            + max(float(item.get("model_score") or 0.0) - 55.0, 0.0) * 0.2
            + max(float(dist_view["expected_excess_return_pct"] or 0.0), 0.0) * 0.45
            - max(float(dist_view["down_probability"] or 0.0) - 35.0, 0.0) * 0.08
        )
        if action in {"exit", "trim"} and item.get("execution_bias") in {"reduce_risk", "capital_preservation"}:
            priority_score += 8.0
        if action in {"new", "add"} and float(item.get("model_score") or 0.0) >= 65.0:
            priority_score += 6.0

        rounded_selected.append(
            {
                **item,
                "target_weight_pct": target_weight_pct,
                "current_weight_pct": current_weight_pct,
                "delta_weight_pct": delta_weight_pct,
                "action": action,
                "priority": _priority_label(priority_score),
                "priority_score": round(priority_score, 2),
                "target_horizon_days": 20,
                "target_date_20d": dist_view["target_date"],
                "expected_return_pct_20d": round(float(dist_view["expected_return_pct"] or 0.0), 2),
                "expected_excess_return_pct_20d": round(float(dist_view["expected_excess_return_pct"] or 0.0), 2),
                "median_return_pct_20d": round(float(dist_view["median_return_pct"] or 0.0), 2),
                "forecast_volatility_pct_20d": round(float(dist_view["forecast_volatility_pct"] or 0.0), 2),
                "up_probability_20d": round(float(dist_view["up_probability"] or 0.0), 2),
                "flat_probability_20d": round(float(dist_view["flat_probability"] or 0.0), 2),
                "down_probability_20d": round(float(dist_view["down_probability"] or 0.0), 2),
                "distribution_confidence_20d": round(float(dist_view["confidence"] or 0.0), 1),
                "raw_confidence_20d": dist_view["raw_confidence"],
                "calibrated_probability_20d": dist_view["calibrated_probability"],
                "probability_edge_20d": dist_view["probability_edge"],
                "analog_support_20d": dist_view["analog_support"],
                "regime_support_20d": dist_view["regime_support"],
                "agreement_support_20d": dist_view["agreement_support"],
                "data_quality_support_20d": dist_view["data_quality_support"],
                "volatility_ratio_20d": dist_view["volatility_ratio"],
                "confidence_calibrator_20d": dist_view["confidence_calibrator"],
                "price_q25_20d": dist_view["bear_case_price"],
                "price_q50_20d": dist_view["base_case_price"],
                "price_q75_20d": dist_view["bull_case_price"],
                "predicted_return_pct": round(float(dist_view["expected_return_pct"] or 0.0), 2),
                "up_probability": round(float(dist_view["up_probability"] or 0.0), 2),
                "bull_case_price": dist_view["bull_case_price"],
                "base_case_price": dist_view["base_case_price"],
                "bear_case_price": dist_view["bear_case_price"],
                "bull_probability": round(float(dist_view["up_probability"] or 0.0), 2),
                "base_probability": round(float(dist_view["flat_probability"] or 0.0), 2),
                "bear_probability": round(float(dist_view["down_probability"] or 0.0), 2),
            }
        )

    return rounded_selected, optimization


def _allocation_breakdown(items: list[dict], field: str) -> list[dict]:
    grouped: dict[str, float] = defaultdict(float)
    for item in items:
        target_weight_pct = float(item.get("target_weight_pct") or 0.0)
        if target_weight_pct <= 0:
            continue
        grouped[str(item.get(field) or "Other")] += target_weight_pct
    return [
        {"name": key, "value": round(value, 2)}
        for key, value in sorted(grouped.items(), key=lambda entry: entry[1], reverse=True)
    ]


async def _build_model_portfolio(
    *,
    user_id: str,
    holdings: list[dict],
    risk: dict,
    country_context: dict[str, dict],
    country_weights: dict[str, float],
    risk_off_weight: float,
) -> dict:
    if not holdings:
        return _portfolio_model_defaults("보유 종목이나 워치리스트를 추가하면 권장 비중과 리밸런싱 큐를 자동으로 계산합니다.")

    budget = _model_budget(
        overall_label=str(risk.get("overall_label") or "moderate"),
        portfolio_up_probability=float(risk.get("portfolio_up_probability") or 50.0),
        risk_off_weight=risk_off_weight,
        downside_watch_weight=float(risk.get("downside_watch_weight") or 0.0),
    )

    watchlist_rows = await supabase_client.watchlist_list(user_id)
    watchlist_keys = {
        f"{row.get('country_code', 'KR')}:{row.get('ticker')}"
        for row in watchlist_rows
        if row.get("ticker")
    }

    base_scan_countries = [item.get("country_code", "KR") for item in holdings]
    base_scan_countries.extend(row.get("country_code", "KR") for row in watchlist_rows)
    scan_countries = _supplement_scan_countries(base_scan_countries)
    radar_responses = await gather_limited(
        scan_countries,
        lambda code: market_service.get_market_opportunities(code, limit=6),
        limit=2,
    )
    radar_items = [
        opportunity
        for response in radar_responses
        if not isinstance(response, Exception)
        for opportunity in response.get("opportunities", [])
    ]
    radar_lookup = {
        f"{item.get('country_code', 'KR')}:{item.get('ticker')}": item
        for item in radar_items
        if item.get("ticker")
    }

    candidates: list[dict] = []
    holding_keys = set()
    for holding in holdings:
        key = f"{holding['country_code']}:{holding['ticker']}"
        holding_keys.add(key)
        radar_match = radar_lookup.get(key)
        model_score, notes = _holding_model_score(holding, radar_match=radar_match)
        candidates.append(
            {
                "key": key,
                "ticker": holding["ticker"],
                "name": holding["name"],
                "country_code": holding["country_code"],
                "sector": holding["sector"],
                "source": "holding",
                "in_watchlist": key in watchlist_keys,
                "current_weight_pct": round(float(holding.get("weight_pct") or 0.0), 2),
                "model_score": model_score,
                "weight_score": max(model_score - 42.0, 6.0) + 2.0,
                "target_horizon_days": 20,
                "target_date_20d": holding.get("target_date_20d"),
                "expected_return_pct_20d": holding.get("expected_return_pct_20d"),
                "expected_excess_return_pct_20d": holding.get("expected_excess_return_pct_20d"),
                "median_return_pct_20d": holding.get("median_return_pct_20d"),
                "forecast_volatility_pct_20d": holding.get("forecast_volatility_pct_20d"),
                "up_probability_20d": holding.get("up_probability_20d"),
                "flat_probability_20d": holding.get("flat_probability_20d"),
                "down_probability_20d": holding.get("down_probability_20d"),
                "distribution_confidence_20d": holding.get("distribution_confidence_20d"),
                "raw_confidence_20d": holding.get("raw_confidence_20d"),
                "calibrated_probability_20d": holding.get("calibrated_probability_20d"),
                "probability_edge_20d": holding.get("probability_edge_20d"),
                "analog_support_20d": holding.get("analog_support_20d"),
                "regime_support_20d": holding.get("regime_support_20d"),
                "agreement_support_20d": holding.get("agreement_support_20d"),
                "data_quality_support_20d": holding.get("data_quality_support_20d"),
                "volatility_ratio_20d": holding.get("volatility_ratio_20d"),
                "confidence_calibrator_20d": holding.get("confidence_calibrator_20d"),
                "price_q25_20d": holding.get("price_q25_20d"),
                "price_q50_20d": holding.get("price_q50_20d"),
                "price_q75_20d": holding.get("price_q75_20d"),
                "up_probability": holding.get("up_probability_20d") or holding.get("up_probability"),
                "predicted_return_pct": holding.get("expected_return_pct_20d") or holding.get("predicted_return_pct"),
                "bull_probability": holding.get("up_probability_20d") or holding.get("bull_probability"),
                "base_probability": holding.get("flat_probability_20d") or holding.get("base_probability"),
                "bear_probability": holding.get("down_probability_20d") or holding.get("bear_probability"),
                "bull_case_price": holding.get("price_q75_20d") or holding.get("bull_case_price"),
                "base_case_price": holding.get("price_q50_20d") or holding.get("base_case_price"),
                "bear_case_price": holding.get("price_q25_20d") or holding.get("bear_case_price"),
                "execution_bias": holding.get("execution_bias"),
                "setup_label": holding.get("trade_setup"),
                "rationale": notes,
                "risk_flags": list(holding.get("risk_flags") or []),
            }
        )

    for opportunity in radar_items:
        key = f"{opportunity.get('country_code', 'KR')}:{opportunity.get('ticker')}"
        if key in holding_keys:
            continue
        model_score, notes, source, confidence_floor_passed = _radar_model_score(opportunity, watchlist_keys)
        if not confidence_floor_passed:
            continue
        if model_score < 52.0 and source != "watchlist":
            continue
        candidates.append(
            {
                "key": key,
                "ticker": opportunity.get("ticker"),
                "name": opportunity.get("name"),
                "country_code": opportunity.get("country_code", "KR"),
                "sector": opportunity.get("sector", "Other"),
                "source": source,
                "in_watchlist": source == "watchlist",
                "confidence_floor_passed": confidence_floor_passed,
                "current_weight_pct": 0.0,
                "model_score": model_score,
                "weight_score": max(model_score - 48.0, 4.0),
                "target_horizon_days": 20,
                "target_date_20d": opportunity.get("target_date_20d"),
                "expected_return_pct_20d": opportunity.get("expected_return_pct_20d"),
                "expected_excess_return_pct_20d": opportunity.get("expected_excess_return_pct_20d"),
                "median_return_pct_20d": opportunity.get("median_return_pct_20d"),
                "forecast_volatility_pct_20d": opportunity.get("forecast_volatility_pct_20d"),
                "up_probability_20d": opportunity.get("up_probability_20d"),
                "flat_probability_20d": opportunity.get("flat_probability_20d"),
                "down_probability_20d": opportunity.get("down_probability_20d"),
                "distribution_confidence_20d": opportunity.get("distribution_confidence_20d"),
                "raw_confidence_20d": opportunity.get("raw_confidence_20d"),
                "calibrated_probability_20d": opportunity.get("calibrated_probability_20d"),
                "probability_edge_20d": opportunity.get("probability_edge_20d"),
                "analog_support_20d": opportunity.get("analog_support_20d"),
                "regime_support_20d": opportunity.get("regime_support_20d"),
                "agreement_support_20d": opportunity.get("agreement_support_20d"),
                "data_quality_support_20d": opportunity.get("data_quality_support_20d"),
                "volatility_ratio_20d": opportunity.get("volatility_ratio_20d"),
                "confidence_calibrator_20d": opportunity.get("confidence_calibrator_20d"),
                "price_q25_20d": opportunity.get("price_q25_20d"),
                "price_q50_20d": opportunity.get("price_q50_20d"),
                "price_q75_20d": opportunity.get("price_q75_20d"),
                "up_probability": opportunity.get("up_probability_20d") or opportunity.get("up_probability"),
                "predicted_return_pct": opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct"),
                "bull_probability": opportunity.get("up_probability_20d") or opportunity.get("bull_probability"),
                "base_probability": opportunity.get("flat_probability_20d") or opportunity.get("base_probability"),
                "bear_probability": opportunity.get("down_probability_20d") or opportunity.get("bear_probability"),
                "bull_case_price": opportunity.get("price_q75_20d") or opportunity.get("bull_case_price"),
                "base_case_price": opportunity.get("price_q50_20d") or opportunity.get("base_case_price"),
                "bear_case_price": opportunity.get("price_q25_20d") or opportunity.get("bear_case_price"),
                "execution_bias": opportunity.get("execution_bias"),
                "setup_label": opportunity.get("setup_label"),
                "rationale": notes,
                "risk_flags": list(opportunity.get("risk_flags") or []),
            }
        )

    selected = _select_model_candidates(candidates, int(budget["target_position_count"]))
    selected = await attach_candidate_return_series(selected, limit=4)
    recommended_holdings, optimization = _allocate_model_weights(selected, budget)
    budget["recommended_equity_pct"] = optimization.actual_equity_pct
    budget["cash_buffer_pct"] = round(100.0 - optimization.actual_equity_pct, 2)

    recommended_lookup = {item["key"]: item for item in recommended_holdings}
    rebalance_actions: list[dict] = []
    for holding in holdings:
        key = f"{holding['country_code']}:{holding['ticker']}"
        item = recommended_lookup.get(key)
        target_weight_pct = float(item.get("target_weight_pct") or 0.0) if item else 0.0
        current_weight_pct = round(float(holding.get("weight_pct") or 0.0), 2)
        delta_weight_pct = round(target_weight_pct - current_weight_pct, 2)
        action = _candidate_action(
            current_weight_pct=current_weight_pct,
            target_weight_pct=target_weight_pct,
            execution_bias=holding.get("execution_bias"),
        )
        priority_score = abs(delta_weight_pct) * 2.4 + max(float(holding.get("risk_score") or 0.0) - 60.0, 0.0) * 0.15
        if action in {"exit", "trim"}:
            priority_score += 5.0
        if holding.get("execution_bias") in {"reduce_risk", "capital_preservation"}:
            priority_score += 4.0
        rebalance_actions.append(
            {
                "ticker": holding["ticker"],
                "name": holding["name"],
                "country_code": holding["country_code"],
                "sector": holding["sector"],
                "source": "holding",
                "in_watchlist": key in watchlist_keys,
                "current_weight_pct": current_weight_pct,
                "target_weight_pct": round(target_weight_pct, 2),
                "delta_weight_pct": delta_weight_pct,
                "model_score": round(float((item or {}).get("model_score") or 0.0), 1),
                "action": action,
                "priority": _priority_label(priority_score),
                "priority_score": round(priority_score, 2),
                "target_horizon_days": 20,
                "target_date_20d": holding.get("target_date_20d"),
                "expected_return_pct_20d": holding.get("expected_return_pct_20d"),
                "expected_excess_return_pct_20d": holding.get("expected_excess_return_pct_20d"),
                "median_return_pct_20d": holding.get("median_return_pct_20d"),
                "forecast_volatility_pct_20d": holding.get("forecast_volatility_pct_20d"),
                "up_probability_20d": holding.get("up_probability_20d"),
                "flat_probability_20d": holding.get("flat_probability_20d"),
                "down_probability_20d": holding.get("down_probability_20d"),
                "distribution_confidence_20d": holding.get("distribution_confidence_20d"),
                "raw_confidence_20d": holding.get("raw_confidence_20d"),
                "calibrated_probability_20d": holding.get("calibrated_probability_20d"),
                "probability_edge_20d": holding.get("probability_edge_20d"),
                "analog_support_20d": holding.get("analog_support_20d"),
                "regime_support_20d": holding.get("regime_support_20d"),
                "agreement_support_20d": holding.get("agreement_support_20d"),
                "data_quality_support_20d": holding.get("data_quality_support_20d"),
                "volatility_ratio_20d": holding.get("volatility_ratio_20d"),
                "confidence_calibrator_20d": holding.get("confidence_calibrator_20d"),
                "price_q25_20d": holding.get("price_q25_20d"),
                "price_q50_20d": holding.get("price_q50_20d"),
                "price_q75_20d": holding.get("price_q75_20d"),
                "up_probability": holding.get("up_probability_20d") or holding.get("up_probability"),
                "predicted_return_pct": holding.get("expected_return_pct_20d") or holding.get("predicted_return_pct"),
                "bull_probability": holding.get("up_probability_20d") or holding.get("bull_probability"),
                "base_probability": holding.get("flat_probability_20d") or holding.get("base_probability"),
                "bear_probability": holding.get("down_probability_20d") or holding.get("bear_probability"),
                "bull_case_price": holding.get("price_q75_20d") or holding.get("bull_case_price"),
                "base_case_price": holding.get("price_q50_20d") or holding.get("base_case_price"),
                "bear_case_price": holding.get("price_q25_20d") or holding.get("bear_case_price"),
                "execution_bias": holding.get("execution_bias"),
                "setup_label": holding.get("trade_setup"),
                "rationale": list((item or {}).get("rationale") or holding.get("thesis") or []),
                "risk_flags": list(holding.get("risk_flags") or []),
            }
        )

    for item in recommended_holdings:
        if item.get("current_weight_pct", 0.0) <= 0.1 and item.get("target_weight_pct", 0.0) >= 3.0:
            priority_score = abs(float(item["delta_weight_pct"])) * 2.1 + max(float(item["model_score"]) - 60.0, 0.0) * 0.22 + 4.0
            rebalance_actions.append(
                {
                    **item,
                    "priority": _priority_label(priority_score),
                    "priority_score": round(priority_score, 2),
                }
            )

    rebalance_actions.sort(key=lambda item: item.get("priority_score", 0.0), reverse=True)

    recommended_holdings.sort(
        key=lambda item: (
            item.get("target_weight_pct", 0.0),
            item.get("model_score", 0.0),
        ),
        reverse=True,
    )

    pipeline = [
        {
            **item,
            "priority": _priority_label(max(float(item.get("model_score") or 0.0) - 45.0, 0.0)),
            "target_weight_pct": 0.0,
            "delta_weight_pct": 0.0,
            "action": "watch",
        }
        for item in sorted(
            (
                candidate for candidate in candidates
                if candidate["source"] != "holding" and candidate["key"] not in recommended_lookup
            ),
            key=lambda entry: entry.get("model_score", 0.0),
            reverse=True,
        )[:4]
    ]

    top_country = _allocation_breakdown(recommended_holdings, "country_code")
    top_sector = _allocation_breakdown(recommended_holdings, "sector")
    trim_count = sum(1 for item in rebalance_actions if item.get("action") in {"trim", "exit"})
    new_position_count = sum(1 for item in recommended_holdings if item.get("current_weight_pct", 0.0) <= 0.1)
    watchlist_focus_count = sum(1 for item in recommended_holdings if item.get("in_watchlist"))

    notes = [
        f"현재 추천안은 `{budget['style_label']}` 운영을 기준으로 주식 {optimization.actual_equity_pct:.1f}% / 현금 {budget['cash_buffer_pct']:.1f}%를 제안합니다.",
        f"권장 포지션 수는 {len(recommended_holdings)}개이며 단일 종목 상단은 {budget['max_single_weight_pct']:.1f}%로 제한했습니다.",
    ]
    if recommended_holdings:
        notes.append(
            f"20거래일 기대수익률 {optimization.expected_return_pct_20d:+.2f}%, 기대초과수익률 {optimization.expected_excess_return_pct_20d:+.2f}%를 기준으로 비중을 최적화했습니다."
        )
        notes.append(
            f"예상 변동성은 {optimization.forecast_volatility_pct_20d:.2f}%, 예상 회전율은 {optimization.turnover_pct:.2f}%입니다."
        )
    if trim_count > 0:
        notes.append(f"현재 보유 종목 중 {trim_count}개는 방어 신호 또는 과대 비중 때문에 먼저 줄이는 편이 좋습니다.")
    if new_position_count > 0:
        notes.append(f"신규 편입 후보 {new_position_count}개를 레이더와 워치리스트에서 추려 모델 포트폴리오에 반영했습니다.")
    defensive_hold_count = sum(
        1 for item in recommended_holdings
        if item.get("execution_bias") in {"reduce_risk", "capital_preservation"} and float(item.get("target_weight_pct") or 0.0) <= 0.1
    )
    if defensive_hold_count > 0:
        notes.append(f"방어 신호가 강한 후보 {defensive_hold_count}개는 목록에 남기되 목표 비중은 0%로 유지해 신규 확대를 막았습니다.")
    if top_country:
        notes.append(f"국가 비중은 {top_country[0]['name']} {top_country[0]['value']:.1f}% 수준에서 관리하도록 설계했습니다.")
    elif not recommended_holdings:
        notes.append("현재 데이터 기준으로 신규 추천안을 구성할 만한 확신 높은 후보가 부족합니다.")

    return {
        "as_of": datetime.now().isoformat(),
        "objective": "20거래일 분포 기대수익률과 기대초과수익률, EWMA+shrinkage 공분산, 회전율 패널티를 함께 반영해 실제 매매 비중 제안으로 연결한 모델 포트폴리오입니다.",
        "risk_budget": budget,
        "summary": {
            "selected_count": len(recommended_holdings),
            "new_position_count": new_position_count,
            "trim_count": trim_count,
            "watchlist_focus_count": watchlist_focus_count,
            "model_up_probability": round(optimization.up_probability_20d, 2),
            "model_predicted_return_pct": round(optimization.expected_return_pct_20d, 2),
            "expected_return_pct_20d": round(optimization.expected_return_pct_20d, 2),
            "expected_excess_return_pct_20d": round(optimization.expected_excess_return_pct_20d, 2),
            "forecast_volatility_pct_20d": round(optimization.forecast_volatility_pct_20d, 2),
            "up_probability_20d": round(optimization.up_probability_20d, 2),
            "down_probability_20d": round(optimization.down_probability_20d, 2),
            "turnover_pct": round(optimization.turnover_pct, 2),
        },
        "allocation": {
            "by_country": top_country,
            "by_sector": top_sector,
        },
        "recommended_holdings": recommended_holdings,
        "rebalance_actions": rebalance_actions[:6],
        "candidate_pipeline": pipeline,
        "notes": notes[:5],
    }


async def get_portfolio(user_id: str):
    """Get portfolio with current prices, risk context, and execution guidance."""
    cache_key = _portfolio_cache_key(user_id)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    profile = await supabase_client.portfolio_profile_get(user_id)
    normalized_profile = {
        "total_assets": round(float(profile.get("total_assets") or 0.0), 2),
        "cash_balance": round(float(profile.get("cash_balance") or 0.0), 2),
        "monthly_budget": round(float(profile.get("monthly_budget") or 0.0), 2),
        "updated_at": profile.get("updated_at"),
    }

    holdings = [
        row
        for row in await supabase_client.portfolio_list(user_id)
        if _normalize_country_code(row.get("country_code", "KR")) == "KR"
    ]
    if not holdings:
        summary = _build_asset_summary(
            profile=normalized_profile,
            total_invested=0.0,
            total_current=0.0,
            total_pnl=0.0,
            holding_count=0,
        )
        empty = {
            "profile": normalized_profile,
            "holdings": [],
            "summary": summary,
            "allocation": {
                "by_sector": [],
                "by_country": [],
            },
            "risk": {
                "overall_label": "empty",
                "score": 0.0,
                "diversification_score": 0.0,
                "concentration_hhi": 0.0,
                "top_holding_weight": 0.0,
                "avg_volatility_pct": 0.0,
                "portfolio_beta": 0.0,
                "portfolio_up_probability": 0.0,
                "projected_next_day_return_pct": 0.0,
                "warning_count": 0,
                "warnings": [],
                "playbook": ["Add holdings to unlock risk coaching, stress testing, and live execution guidance."],
                "regimes": [],
                "downside_watch_weight": 0.0,
                "bearish_scenario_exposure": 0.0,
                "execution_mix": [],
                "action_queue": [],
            },
            "stress_test": [],
            "model_portfolio": _portfolio_model_defaults(
                "보유 종목이나 워치리스트를 추가하면 권장 비중과 리밸런싱 큐를 자동으로 계산합니다."
            ),
        }
        await cache.set(cache_key, empty, 60)
        return empty

    unique_countries = sorted(
        {
            row.get("country_code", "KR")
            for row in holdings
            if row.get("country_code", "KR") in COUNTRY_REGISTRY
        }
    )

    async def _load_country_context(country_code: str) -> tuple[str, dict]:
        index = COUNTRY_REGISTRY[country_code].indices[0]
        history = await yfinance_client.get_price_history(index.ticker, period="6mo")
        macro_snapshot = await ecos_client.get_kr_economic_snapshot() if country_code == "KR" else {}
        kosis_snapshot = await kosis_client.get_kr_macro_snapshot() if country_code == "KR" else {}
        regime_forecast = forecast_next_day(
            ticker=index.ticker,
            name=index.name,
            country_code=country_code,
            price_history=history,
            benchmark_history=history,
            macro_snapshot=macro_snapshot,
            kosis_snapshot=kosis_snapshot,
            asset_type="index",
        )
        regime = build_market_regime(
            country_code=country_code,
            name=index.name,
            price_history=history,
            next_day_forecast=regime_forecast,
        )
        return country_code, {
            "benchmark_ticker": index.ticker,
            "benchmark_name": index.name,
            "benchmark_history": history,
            "market_regime": regime,
            "market_forecast": regime_forecast,
            "macro_snapshot": macro_snapshot,
            "kosis_snapshot": kosis_snapshot,
        }

    country_results = await gather_limited(unique_countries, _load_country_context, limit=3)
    country_context = {
        country_code: payload
        for item in country_results
        if not isinstance(item, Exception)
        for country_code, payload in [item]
    }

    async def _enrich_holding(holding: dict) -> dict:
        country_code = _normalize_country_code(holding.get("country_code", "KR"))
        ticker = normalize_portfolio_ticker(holding["ticker"], country_code)
        if ticker != holding.get("ticker") or country_code != holding.get("country_code"):
            try:
                await supabase_client.portfolio_update_identity(user_id, holding["id"], ticker, country_code)
            except Exception:
                pass
        context = country_context.get(country_code)
        benchmark_history = context.get("benchmark_history") if context else []
        market_regime = context.get("market_regime") if context else None
        macro_snapshot = context.get("macro_snapshot") if context else {}
        kosis_snapshot = context.get("kosis_snapshot") if context else {}

        try:
            info, analyst_raw, price_history = await asyncio.gather(
                yfinance_client.get_stock_info(ticker),
                yfinance_client.get_analyst_ratings(ticker),
                yfinance_client.get_price_history(ticker, period="6mo"),
            )
        except Exception:
            info = {"current_price": holding["buy_price"], "name": holding.get("name") or ticker, "sector": "Unknown"}
            analyst_raw = {}
            price_history = []

        current_price = float(info.get("current_price") or holding["buy_price"])
        sector = info.get("sector", "Other")
        invested = holding["buy_price"] * holding["quantity"]
        current_value = current_price * holding["quantity"]
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100.0) if invested else 0.0

        price_points = [PricePoint(**row) for row in price_history if {"date", "open", "high", "low", "close", "volume"} <= set(row)]
        technical = _calc_technicals(price_history)
        buy_sell = build_quick_buy_sell(info)
        next_day_forecast = forecast_next_day(
            ticker=ticker,
            name=info.get("name", ticker),
            country_code=country_code,
            price_history=price_history,
            analyst_context={
                **analyst_raw,
                "target_mean": info.get("target_mean"),
                "target_median": info.get("target_median"),
                "target_high": info.get("target_high"),
                "target_low": info.get("target_low"),
            },
            context_bias=0.18 if market_regime and market_regime.stance == "risk_on" else -0.18 if market_regime and market_regime.stance == "risk_off" else 0.0,
            asset_type="stock",
            benchmark_history=benchmark_history,
            macro_snapshot=macro_snapshot,
            kosis_snapshot=kosis_snapshot,
            fundamental_context=info,
        ) if price_history else None
        distributional_forecast = build_distributional_forecast(
            price_history=price_history,
            benchmark_history=benchmark_history,
            macro_snapshot=macro_snapshot,
            kosis_snapshot=kosis_snapshot,
            analyst_context={
                **analyst_raw,
                "target_mean": info.get("target_mean"),
                "target_median": info.get("target_median"),
                "target_high": info.get("target_high"),
                "target_low": info.get("target_low"),
            },
            fundamental_context=info,
            asset_type="stock",
        ) if price_history else None
        trade_plan = build_trade_plan(
            ticker=ticker,
            current_price=current_price,
            price_history=price_points,
            technical=technical,
            buy_sell_guide=buy_sell,
            next_day_forecast=next_day_forecast,
            market_regime=market_regime,
        ) if price_points else None
        scenario_snapshot = _scenario_snapshot(next_day_forecast) if next_day_forecast else {}
        horizon_20 = build_horizon_snapshot(
            distributional_forecast,
            horizon_days=20,
            country_code=country_code,
        )

        realized_volatility_pct = _annualized_volatility(price_history)
        max_drawdown_pct = _max_drawdown(price_history)
        beta = _beta(price_history, benchmark_history) if benchmark_history else None

        risk_score = 30.0
        risk_score += min(realized_volatility_pct, 60.0) * 0.55
        risk_score += min(max_drawdown_pct, 35.0) * 0.35
        if beta is not None:
            risk_score += max(beta - 1.0, 0.0) * 8.0
        if market_regime and market_regime.stance == "risk_off":
            risk_score += 8.0
        if next_day_forecast and next_day_forecast.direction == "down":
            risk_score += 10.0
        if trade_plan and trade_plan.action == "reduce_risk":
            risk_score += 12.0
        risk_score = round(_clip(risk_score, 15.0, 95.0), 1)

        return {
            "id": holding["id"],
            "ticker": ticker,
            "name": info.get("name") or holding.get("name") or ticker,
            "country_code": country_code,
            "sector": sector,
            "buy_price": holding["buy_price"],
            "current_price": round(current_price, 2),
            "quantity": holding["quantity"],
            "buy_date": holding["buy_date"],
            "invested": round(invested, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "realized_volatility_pct": round(realized_volatility_pct, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "beta": round(beta, 2) if beta is not None else None,
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
            "up_probability": round(next_day_forecast.up_probability, 2) if next_day_forecast else None,
            "predicted_return_pct": round(next_day_forecast.predicted_return_pct, 2) if next_day_forecast else None,
            "forecast_date": next_day_forecast.target_date if next_day_forecast else None,
            "target_horizon_days": 20,
            "target_date_20d": horizon_20.get("target_date"),
            "expected_return_pct_20d": horizon_20.get("expected_return_pct"),
            "expected_excess_return_pct_20d": horizon_20.get("expected_excess_return_pct"),
            "median_return_pct_20d": horizon_20.get("median_return_pct"),
            "forecast_volatility_pct_20d": horizon_20.get("forecast_volatility_pct"),
            "up_probability_20d": horizon_20.get("up_probability"),
            "flat_probability_20d": horizon_20.get("flat_probability"),
            "down_probability_20d": horizon_20.get("down_probability"),
            "distribution_confidence_20d": horizon_20.get("confidence"),
            "raw_confidence_20d": horizon_20.get("raw_confidence"),
            "calibrated_probability_20d": horizon_20.get("calibrated_probability"),
            "probability_edge_20d": horizon_20.get("probability_edge"),
            "analog_support_20d": horizon_20.get("analog_support"),
            "regime_support_20d": horizon_20.get("regime_support"),
            "agreement_support_20d": horizon_20.get("agreement_support"),
            "data_quality_support_20d": horizon_20.get("data_quality_support"),
            "volatility_ratio_20d": horizon_20.get("volatility_ratio"),
            "confidence_calibrator_20d": horizon_20.get("confidence_calibrator"),
            "price_q25_20d": horizon_20.get("price_q25"),
            "price_q50_20d": horizon_20.get("price_q50"),
            "price_q75_20d": horizon_20.get("price_q75"),
            "execution_bias": next_day_forecast.execution_bias if next_day_forecast else None,
            "execution_note": next_day_forecast.execution_note if next_day_forecast else None,
            "risk_flags": (next_day_forecast.risk_flags[:2] if next_day_forecast else []),
            "bull_case_price": scenario_snapshot.get("bull_case_price"),
            "base_case_price": scenario_snapshot.get("base_case_price"),
            "bear_case_price": scenario_snapshot.get("bear_case_price"),
            "bull_probability": scenario_snapshot.get("bull_probability"),
            "base_probability": scenario_snapshot.get("base_probability"),
            "bear_probability": scenario_snapshot.get("bear_probability"),
            "trade_action": trade_plan.action if trade_plan else None,
            "trade_setup": trade_plan.setup_label if trade_plan else None,
            "trade_conviction": trade_plan.conviction if trade_plan else None,
            "entry_low": trade_plan.entry_low if trade_plan else None,
            "entry_high": trade_plan.entry_high if trade_plan else None,
            "stop_loss": trade_plan.stop_loss if trade_plan else None,
            "take_profit_1": trade_plan.take_profit_1 if trade_plan else None,
            "take_profit_2": trade_plan.take_profit_2 if trade_plan else None,
            "market_regime_label": market_regime.label if market_regime else None,
            "market_regime_stance": market_regime.stance if market_regime else None,
            "thesis": trade_plan.thesis[:2] if trade_plan else [],
        }

    enriched_results = await gather_limited(holdings, _enrich_holding, limit=4)
    enriched = [row for row in enriched_results if not isinstance(row, Exception)]

    total_invested = sum(item["invested"] for item in enriched)
    total_current = sum(item["current_value"] for item in enriched)
    total_pnl = total_current - total_invested

    sectors: dict[str, float] = defaultdict(float)
    countries: dict[str, float] = defaultdict(float)
    for item in enriched:
        sectors[item["sector"]] += item["current_value"]
        countries[item["country_code"]] += item["current_value"]

    for item in enriched:
        weight = (item["current_value"] / total_current * 100.0) if total_current else 0.0
        item["weight_pct"] = round(weight, 2)
        item["risk_score"] = round(_clip(item["risk_score"] + max(weight - 18.0, 0.0) * 0.75, 15.0, 98.0), 1)
        item["risk_level"] = _risk_level(item["risk_score"])

    enriched.sort(key=lambda item: item["current_value"], reverse=True)

    country_weights = {country: value / total_current * 100.0 for country, value in countries.items()} if total_current else {}
    top_holding_weight = max((item["weight_pct"] for item in enriched), default=0.0)
    concentration_hhi = sum((item["weight_pct"] / 100.0) ** 2 for item in enriched)
    diversification_score = round(_clip((1.0 - concentration_hhi) * 130.0, 0.0, 100.0), 1)
    avg_volatility_pct = sum(item["realized_volatility_pct"] * item["current_value"] for item in enriched) / total_current if total_current else 0.0
    beta_weights = [item for item in enriched if item["beta"] is not None]
    portfolio_beta = (
        sum(item["beta"] * item["current_value"] for item in beta_weights) / sum(item["current_value"] for item in beta_weights)
        if beta_weights else 0.0
    )
    portfolio_up_probability = sum((item["up_probability"] or 50.0) * item["current_value"] for item in enriched) / total_current if total_current else 50.0
    projected_next_day_pct = sum((item["predicted_return_pct"] or 0.0) * item["current_value"] for item in enriched) / total_current if total_current else 0.0
    bearish_scenario_exposure = (
        sum((item.get("bear_probability") or 0.0) * item["current_value"] for item in enriched) / total_current
        if total_current else 0.0
    )
    downside_watch_weight = sum(
        item["weight_pct"]
        for item in enriched
        if item.get("execution_bias") in {"reduce_risk", "capital_preservation"}
        or (item.get("bear_probability") or 0.0) >= 28.0
    )

    warnings: list[str] = []
    if top_holding_weight >= 35:
        warnings.append(f"Top position concentration is elevated at {top_holding_weight:.1f}% of portfolio value.")
    largest_sector_weight = max((value / total_current * 100.0 for value in sectors.values()), default=0.0) if total_current else 0.0
    if largest_sector_weight >= 45:
        warnings.append(f"Largest sector sleeve accounts for {largest_sector_weight:.1f}% of the book.")
    if portfolio_up_probability < 48:
        warnings.append("Portfolio-level next-session odds lean defensive, with fewer bullish forecasts than bearish ones.")
    risk_off_weight = sum(
        weight for country_code, weight in country_weights.items()
        if country_context.get(country_code, {}).get("market_regime") and country_context[country_code]["market_regime"].stance == "risk_off"
    )
    if risk_off_weight >= 40:
        warnings.append(f"{risk_off_weight:.1f}% of capital sits in markets currently flagged as risk-off.")
    high_risk_count = sum(1 for item in enriched if item["risk_level"] == "high")
    if high_risk_count >= max(2, math.ceil(len(enriched) / 2)):
        warnings.append("A large share of holdings now fall into the high-risk bucket based on volatility, drawdown, and market backdrop.")
    if downside_watch_weight >= 35:
        warnings.append(f"{downside_watch_weight:.1f}% of the portfolio sits in names that currently lean defensive on the execution layer.")
    if bearish_scenario_exposure >= 26:
        warnings.append(f"Bear-case probability exposure is elevated at {bearish_scenario_exposure:.1f}%, so downside scenarios deserve active monitoring.")

    playbook: list[str] = []
    if top_holding_weight >= 30:
        playbook.append("Trim the largest winner or laggard into strength to bring the top position closer to a 20-25% weight.")
    if risk_off_weight >= 40:
        playbook.append("Reduce cyclical exposure in the most defensive country sleeve first and keep fresh adds smaller than usual.")
    if portfolio_up_probability >= 55 and diversification_score >= 55:
        playbook.append("Conditions are constructive enough to add selectively, but prioritize holdings with accumulate/breakout-watch actions only.")
    else:
        playbook.append("Stay size-aware and demand clean entries; avoid chasing names already above their preferred buy bands.")
    if largest_sector_weight >= 40:
        playbook.append("Use new capital to diversify away from the dominant sector instead of averaging deeper into the same theme.")
    if downside_watch_weight >= 35:
        playbook.append("Prioritize the defensive queue first: review names flagged for reduce-risk or capital-preservation before adding new exposure.")

    concentration_penalty = max(top_holding_weight / 100.0 - 0.22, 0.0)
    execution_mix = _execution_mix(enriched)
    action_queue = _action_queue(enriched)
    stress_test = _stress_scenarios(
        total_current=total_current,
        total_invested=total_invested,
        portfolio_beta=portfolio_beta,
        avg_volatility_pct=avg_volatility_pct,
        projected_next_day_pct=projected_next_day_pct,
        concentration_penalty=concentration_penalty,
    )

    risk_score = 100.0 - diversification_score
    risk_score += max(avg_volatility_pct - 18.0, 0.0) * 0.9
    risk_score += max(portfolio_beta - 1.0, 0.0) * 10.0
    risk_score += max(50.0 - portfolio_up_probability, 0.0) * 0.8
    risk_score += concentration_penalty * 45.0
    risk_score = round(_clip(risk_score, 8.0, 96.0), 1)

    if risk_score >= 72:
        overall_label = "aggressive"
    elif risk_score >= 55:
        overall_label = "elevated"
    elif risk_score <= 32:
        overall_label = "balanced"
    else:
        overall_label = "moderate"

    sector_alloc = [{"name": key, "value": round(value, 2)} for key, value in sorted(sectors.items(), key=lambda item: item[1], reverse=True)]
    country_alloc = [{"name": key, "value": round(value, 2)} for key, value in sorted(countries.items(), key=lambda item: item[1], reverse=True)]
    summary = _build_asset_summary(
        profile=normalized_profile,
        total_invested=total_invested,
        total_current=total_current,
        total_pnl=total_pnl,
        holding_count=len(enriched),
    )

    response = {
        "profile": normalized_profile,
        "holdings": enriched,
        "summary": summary,
        "allocation": {
            "by_sector": sector_alloc,
            "by_country": country_alloc,
        },
        "risk": {
            "overall_label": overall_label,
            "score": risk_score,
            "diversification_score": diversification_score,
            "concentration_hhi": round(concentration_hhi, 4),
            "top_holding_weight": round(top_holding_weight, 2),
            "avg_volatility_pct": round(avg_volatility_pct, 2),
            "portfolio_beta": round(portfolio_beta, 2),
            "portfolio_up_probability": round(portfolio_up_probability, 2),
            "projected_next_day_return_pct": round(projected_next_day_pct, 2),
            "warning_count": len(warnings),
            "warnings": warnings,
            "playbook": playbook,
            "regimes": _regime_weight_summary(country_context, country_weights),
            "downside_watch_weight": round(downside_watch_weight, 2),
            "bearish_scenario_exposure": round(bearish_scenario_exposure, 2),
            "execution_mix": execution_mix,
            "action_queue": action_queue,
        },
        "stress_test": stress_test,
    }
    response["model_portfolio"] = await _build_model_portfolio(
        user_id=user_id,
        holdings=enriched,
        risk=response["risk"],
        country_context=country_context,
        country_weights=country_weights,
        risk_off_weight=risk_off_weight,
    )
    await cache.set(cache_key, response, 90)
    return response


async def add_holding(user_id: str, ticker: str, buy_price: float, quantity: float, buy_date: str, country_code: str = "KR"):
    payload = validate_portfolio_holding_input(ticker, buy_price, quantity, buy_date, country_code)
    normalized_ticker = str(payload["ticker"])
    normalized_country = str(payload["country_code"])
    try:
        info = await yfinance_client.get_stock_info(normalized_ticker)
        name = info.get("name", normalized_ticker)
    except Exception:
        name = normalized_ticker
    await supabase_client.portfolio_add(
        user_id,
        normalized_ticker,
        name,
        normalized_country,
        float(payload["buy_price"]),
        float(payload["quantity"]),
        str(payload["buy_date"]),
    )
    await invalidate_portfolio_cache(user_id)
    return {
        "ticker": normalized_ticker,
        "name": name,
        "country_code": normalized_country,
        "buy_date": str(payload["buy_date"]),
    }


async def update_holding(
    user_id: str,
    holding_id: int,
    ticker: str,
    buy_price: float,
    quantity: float,
    buy_date: str,
    country_code: str = "KR",
):
    payload = validate_portfolio_holding_input(ticker, buy_price, quantity, buy_date, country_code)
    normalized_ticker = str(payload["ticker"])
    normalized_country = str(payload["country_code"])
    try:
        info = await yfinance_client.get_stock_info(normalized_ticker)
        name = info.get("name", normalized_ticker)
    except Exception:
        name = normalized_ticker
    await supabase_client.portfolio_update(
        user_id,
        holding_id,
        normalized_ticker,
        name,
        normalized_country,
        float(payload["buy_price"]),
        float(payload["quantity"]),
        str(payload["buy_date"]),
    )
    await invalidate_portfolio_cache(user_id)
    return {
        "ticker": normalized_ticker,
        "name": name,
        "country_code": normalized_country,
        "buy_date": str(payload["buy_date"]),
    }


async def get_portfolio_profile(user_id: str):
    profile = await supabase_client.portfolio_profile_get(user_id)
    return {
        "total_assets": round(float(profile.get("total_assets") or 0.0), 2),
        "cash_balance": round(float(profile.get("cash_balance") or 0.0), 2),
        "monthly_budget": round(float(profile.get("monthly_budget") or 0.0), 2),
        "updated_at": profile.get("updated_at"),
    }


async def update_portfolio_profile(user_id: str, total_assets: float, cash_balance: float, monthly_budget: float):
    payload = validate_portfolio_profile_input(total_assets, cash_balance, monthly_budget)
    await supabase_client.portfolio_profile_upsert(
        user_id,
        payload["total_assets"],
        payload["cash_balance"],
        payload["monthly_budget"],
    )
    await invalidate_portfolio_cache(user_id)
    return await get_portfolio_profile(user_id)


async def remove_holding(user_id: str, holding_id: int):
    await supabase_client.portfolio_delete(user_id, holding_id)
    await invalidate_portfolio_cache(user_id)
