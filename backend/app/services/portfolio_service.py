from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from datetime import datetime

from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.stock_analyzer import _calc_technicals
from app.analysis.trade_planner import build_trade_plan
from app.analysis.valuation_blend import build_quick_buy_sell
from app.data import cache, yfinance_client
from app.database import db
from app.models.country import COUNTRY_REGISTRY
from app.models.stock import PricePoint
from app.services import market_service
from app.utils.async_tools import gather_limited


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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
        "objective": "예측 시나리오, 실행 바이어스, 포지션 캡을 함께 반영한 모델 포트폴리오 제안입니다.",
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

    for fallback in ["KR", "US", "JP"]:
        if fallback not in ordered:
            ordered.append(fallback)
        if len(ordered) >= 2:
            break

    return ordered[:2]


def _candidate_action(
    *,
    current_weight_pct: float,
    target_weight_pct: float,
) -> str:
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


def _holding_model_score(holding: dict, radar_match: dict | None = None) -> tuple[float, list[str]]:
    up_probability = float(holding.get("up_probability") or (radar_match or {}).get("up_probability") or 50.0)
    predicted_return_pct = float(holding.get("predicted_return_pct") or (radar_match or {}).get("predicted_return_pct") or 0.0)
    trade_conviction = float(holding.get("trade_conviction") or 50.0)
    risk_score = float(holding.get("risk_score") or 50.0)
    bear_probability = float(holding.get("bear_probability") or (radar_match or {}).get("bear_probability") or 0.0)
    execution_bias = holding.get("execution_bias") or (radar_match or {}).get("execution_bias") or "stay_selective"
    trade_action = holding.get("trade_action") or (radar_match or {}).get("action") or "wait_pullback"

    score = 50.0
    score += (up_probability - 50.0) * 0.85
    score += predicted_return_pct * 6.0
    score += (trade_conviction - 50.0) * 0.22
    score += {
        "press_long": 12.0,
        "lean_long": 7.0,
        "stay_selective": 2.0,
        "reduce_risk": -8.0,
        "capital_preservation": -14.0,
    }.get(execution_bias, 0.0)
    score += {
        "accumulate": 8.0,
        "breakout_watch": 5.0,
        "wait_pullback": 1.5,
        "reduce_risk": -6.0,
        "avoid": -8.0,
    }.get(trade_action, 0.0)
    score -= max(risk_score - 55.0, 0.0) * 0.55
    score -= max(bear_probability - 24.0, 0.0) * 0.65

    if holding.get("market_regime_stance") == "risk_on":
        score += 4.0
    elif holding.get("market_regime_stance") == "risk_off":
        score -= 5.5

    if radar_match:
        score += max(float(radar_match.get("opportunity_score") or 0.0) - 60.0, 0.0) * 0.12

    notes = [
        f"다음 거래일 상승 확률 {up_probability:.1f}%, 예상 수익률 {predicted_return_pct:+.2f}%를 반영했습니다.",
        f"실행 바이어스는 `{execution_bias}`이며 현재 셋업은 `{trade_action}` 기준으로 해석했습니다.",
    ]
    risk_flags = holding.get("risk_flags") or []
    thesis = holding.get("thesis") or []
    if risk_flags:
        notes.append(risk_flags[0])
    elif thesis:
        notes.append(thesis[0])

    return round(_clip(score, 0.0, 100.0), 1), notes[:3]


def _radar_model_score(opportunity: dict, watchlist_keys: set[str]) -> tuple[float, list[str], str]:
    watchlist_key = f"{opportunity.get('country_code', 'US')}:{opportunity.get('ticker')}"
    is_watchlist = watchlist_key in watchlist_keys
    execution_bias = opportunity.get("execution_bias") or "stay_selective"
    action = opportunity.get("action") or "wait_pullback"

    score = float(opportunity.get("opportunity_score") or 0.0)
    if is_watchlist:
        score += 5.0
    if action in {"accumulate", "breakout_watch"}:
        score += 3.5
    if execution_bias in {"reduce_risk", "capital_preservation"}:
        score -= 6.0
    if opportunity.get("regime_tailwind") == "tailwind":
        score += 3.0
    elif opportunity.get("regime_tailwind") == "headwind":
        score -= 2.5

    notes = [
        f"Radar Score {float(opportunity.get('opportunity_score') or 0.0):.1f}, 상승 확률 {float(opportunity.get('up_probability') or 0.0):.1f}%입니다.",
        f"실행 바이어스 `{execution_bias}`와 액션 `{action}` 기준으로 신규 편입 후보로 평가했습니다.",
    ]
    if is_watchlist:
        notes.append("워치리스트에 있던 종목이라 우선순위를 한 단계 높였습니다.")
    risk_flags = opportunity.get("risk_flags") or []
    thesis = opportunity.get("thesis") or []
    if risk_flags:
        notes.append(risk_flags[0])
    elif thesis:
        notes.append(thesis[0])

    return round(_clip(score, 0.0, 100.0), 1), notes[:3], "watchlist" if is_watchlist else "radar"


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
        if candidate.get("source") != "holding" and candidate.get("execution_bias") in {"reduce_risk", "capital_preservation"}:
            continue
        minimum_score = 48.0 if candidate.get("source") == "holding" else 56.0
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

    return selected


def _allocate_model_weights(selected: list[dict], budget: dict) -> tuple[list[dict], float]:
    if not selected:
        return [], 0.0

    target_equity_pct = float(budget["recommended_equity_pct"])
    max_single = float(budget["max_single_weight_pct"])
    max_country = float(budget["max_country_weight_pct"])
    max_sector = float(budget["max_sector_weight_pct"])

    targets: dict[str, float] = {item["key"]: 0.0 for item in selected}
    country_alloc: dict[str, float] = defaultdict(float)
    sector_alloc: dict[str, float] = defaultdict(float)

    min_position = max(min(target_equity_pct * 0.58 / max(len(selected), 1), 8.0), 4.0)
    for item in sorted(selected, key=lambda entry: entry.get("model_score", 0.0), reverse=True):
        remaining_total = target_equity_pct - sum(targets.values())
        if remaining_total <= 0.25:
            break
        country_room = max_country - country_alloc[item["country_code"]]
        sector_room = max_sector - sector_alloc[item["sector"]]
        room = min(max_single - targets[item["key"]], country_room, sector_room, remaining_total)
        if room <= 0.25:
            continue
        add_weight = min(min_position, room)
        targets[item["key"]] += add_weight
        country_alloc[item["country_code"]] += add_weight
        sector_alloc[item["sector"]] += add_weight

    remaining = target_equity_pct - sum(targets.values())
    for _ in range(6):
        if remaining <= 0.25:
            break
        active: list[tuple[dict, float]] = []
        for item in selected:
            country_room = max_country - country_alloc[item["country_code"]]
            sector_room = max_sector - sector_alloc[item["sector"]]
            room = min(max_single - targets[item["key"]], country_room, sector_room, remaining)
            if room > 0.1:
                active.append((item, room))
        if not active:
            break

        total_weight_score = sum(max(float(item.get("weight_score") or 0.0), 1.0) for item, _ in active)
        distributed = 0.0
        for item, room in active:
            share = remaining * max(float(item.get("weight_score") or 0.0), 1.0) / total_weight_score
            add_weight = min(share, room)
            if add_weight <= 0.05:
                continue
            targets[item["key"]] += add_weight
            country_alloc[item["country_code"]] += add_weight
            sector_alloc[item["sector"]] += add_weight
            distributed += add_weight
        remaining -= distributed
        if distributed <= 0.1:
            break

    rounded_selected: list[dict] = []
    for item in selected:
        target_weight_pct = round(targets[item["key"]], 2)
        current_weight_pct = round(float(item.get("current_weight_pct") or 0.0), 2)
        delta_weight_pct = round(target_weight_pct - current_weight_pct, 2)
        action = _candidate_action(
            current_weight_pct=current_weight_pct,
            target_weight_pct=target_weight_pct,
        )
        priority_score = abs(delta_weight_pct) * 2.0 + max(float(item.get("model_score") or 0.0) - 55.0, 0.0) * 0.2
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
            }
        )

    actual_equity_pct = round(sum(item["target_weight_pct"] for item in rounded_selected), 2)
    return rounded_selected, actual_equity_pct


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

    watchlist_rows = await db.watchlist_list()
    watchlist_keys = {
        f"{row.get('country_code', 'US')}:{row.get('ticker')}"
        for row in watchlist_rows
        if row.get("ticker")
    }

    base_scan_countries = [item.get("country_code", "US") for item in holdings]
    base_scan_countries.extend(row.get("country_code", "US") for row in watchlist_rows)
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
        f"{item.get('country_code', 'US')}:{item.get('ticker')}": item
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
                "up_probability": holding.get("up_probability"),
                "predicted_return_pct": holding.get("predicted_return_pct"),
                "bull_probability": holding.get("bull_probability"),
                "bear_probability": holding.get("bear_probability"),
                "execution_bias": holding.get("execution_bias"),
                "setup_label": holding.get("trade_setup"),
                "rationale": notes,
                "risk_flags": list(holding.get("risk_flags") or []),
            }
        )

    for opportunity in radar_items:
        key = f"{opportunity.get('country_code', 'US')}:{opportunity.get('ticker')}"
        if key in holding_keys:
            continue
        model_score, notes, source = _radar_model_score(opportunity, watchlist_keys)
        if model_score < 52.0 and source != "watchlist":
            continue
        candidates.append(
            {
                "key": key,
                "ticker": opportunity.get("ticker"),
                "name": opportunity.get("name"),
                "country_code": opportunity.get("country_code", "US"),
                "sector": opportunity.get("sector", "Other"),
                "source": source,
                "in_watchlist": source == "watchlist",
                "current_weight_pct": 0.0,
                "model_score": model_score,
                "weight_score": max(model_score - 48.0, 4.0),
                "up_probability": opportunity.get("up_probability"),
                "predicted_return_pct": opportunity.get("predicted_return_pct"),
                "bull_probability": opportunity.get("bull_probability"),
                "bear_probability": opportunity.get("bear_probability"),
                "execution_bias": opportunity.get("execution_bias"),
                "setup_label": opportunity.get("setup_label"),
                "rationale": notes,
                "risk_flags": list(opportunity.get("risk_flags") or []),
            }
        )

    selected = _select_model_candidates(candidates, int(budget["target_position_count"]))
    recommended_holdings, actual_equity_pct = _allocate_model_weights(selected, budget)
    budget["recommended_equity_pct"] = actual_equity_pct
    budget["cash_buffer_pct"] = round(100.0 - actual_equity_pct, 2)

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
                "up_probability": holding.get("up_probability"),
                "predicted_return_pct": holding.get("predicted_return_pct"),
                "bull_probability": holding.get("bull_probability"),
                "bear_probability": holding.get("bear_probability"),
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

    recommendation_total = sum(float(item.get("target_weight_pct") or 0.0) for item in recommended_holdings)
    weighted_up_probability = (
        sum(float(item.get("up_probability") or 50.0) * float(item.get("target_weight_pct") or 0.0) for item in recommended_holdings) / recommendation_total
        if recommendation_total else 0.0
    )
    weighted_predicted_return = (
        sum(float(item.get("predicted_return_pct") or 0.0) * float(item.get("target_weight_pct") or 0.0) for item in recommended_holdings) / recommendation_total
        if recommendation_total else 0.0
    )

    top_country = _allocation_breakdown(recommended_holdings, "country_code")
    top_sector = _allocation_breakdown(recommended_holdings, "sector")
    trim_count = sum(1 for item in rebalance_actions if item.get("action") in {"trim", "exit"})
    new_position_count = sum(1 for item in recommended_holdings if item.get("current_weight_pct", 0.0) <= 0.1)
    watchlist_focus_count = sum(1 for item in recommended_holdings if item.get("in_watchlist"))

    notes = [
        f"현재 추천안은 `{budget['style_label']}` 운영을 기준으로 주식 {actual_equity_pct:.1f}% / 현금 {budget['cash_buffer_pct']:.1f}%를 제안합니다.",
        f"권장 포지션 수는 {len(recommended_holdings)}개이며 단일 종목 상단은 {budget['max_single_weight_pct']:.1f}%로 제한했습니다.",
    ]
    if trim_count > 0:
        notes.append(f"현재 보유 종목 중 {trim_count}개는 방어 신호 또는 과대 비중 때문에 먼저 줄이는 편이 좋습니다.")
    if new_position_count > 0:
        notes.append(f"신규 편입 후보 {new_position_count}개를 레이더와 워치리스트에서 추려 모델 포트폴리오에 반영했습니다.")
    if top_country:
        notes.append(f"국가 비중은 {top_country[0]['name']} {top_country[0]['value']:.1f}% 수준에서 관리하도록 설계했습니다.")
    elif not recommended_holdings:
        notes.append("현재 데이터 기준으로 신규 추천안을 구성할 만한 확신 높은 후보가 부족합니다.")

    return {
        "as_of": datetime.now().isoformat(),
        "objective": "예측 시나리오, 실행 바이어스, 포지션 캡을 동시에 반영해 실제 매매 비중 제안으로 연결한 모델 포트폴리오입니다.",
        "risk_budget": budget,
        "summary": {
            "selected_count": len(recommended_holdings),
            "new_position_count": new_position_count,
            "trim_count": trim_count,
            "watchlist_focus_count": watchlist_focus_count,
            "model_up_probability": round(weighted_up_probability, 2),
            "model_predicted_return_pct": round(weighted_predicted_return, 2),
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


async def get_portfolio():
    """Get portfolio with current prices, risk context, and execution guidance."""
    cache_key = "portfolio_overview:v5"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    holdings = await db.portfolio_list()
    if not holdings:
        empty = {
            "holdings": [],
            "summary": {
                "total_invested": 0.0,
                "total_current": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0,
                "holding_count": 0,
            },
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

    unique_countries = sorted({row.get("country_code", "US") for row in holdings if row.get("country_code", "US") in COUNTRY_REGISTRY})

    async def _load_country_context(country_code: str) -> tuple[str, dict]:
        index = COUNTRY_REGISTRY[country_code].indices[0]
        history = await yfinance_client.get_price_history(index.ticker, period="6mo")
        regime_forecast = forecast_next_day(
            ticker=index.ticker,
            name=index.name,
            country_code=country_code,
            price_history=history,
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
        }

    country_results = await gather_limited(unique_countries, _load_country_context, limit=3)
    country_context = {
        country_code: payload
        for item in country_results
        if not isinstance(item, Exception)
        for country_code, payload in [item]
    }

    async def _enrich_holding(holding: dict) -> dict:
        ticker = holding["ticker"]
        country_code = holding.get("country_code", "US")
        context = country_context.get(country_code)
        benchmark_history = context.get("benchmark_history") if context else []
        market_regime = context.get("market_regime") if context else None

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
            "name": holding.get("name") or info.get("name", ticker),
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
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested else 0.0

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

    response = {
        "holdings": enriched,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "holding_count": len(enriched),
        },
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
        holdings=enriched,
        risk=response["risk"],
        country_context=country_context,
        country_weights=country_weights,
        risk_off_weight=risk_off_weight,
    )
    await cache.set(cache_key, response, 90)
    return response


async def add_holding(ticker: str, buy_price: float, quantity: float, buy_date: str, country_code: str = "US"):
    try:
        info = await yfinance_client.get_stock_info(ticker)
        name = info.get("name", ticker)
    except Exception:
        name = ticker
    await db.portfolio_add(ticker, name, country_code, buy_price, quantity, buy_date)
    await cache.invalidate("portfolio_overview:%")


async def remove_holding(holding_id: int):
    await db.portfolio_delete(holding_id)
    await cache.invalidate("portfolio_overview:%")
