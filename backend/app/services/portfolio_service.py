from __future__ import annotations

import asyncio
import math
from collections import defaultdict

from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.stock_analyzer import _calc_technicals
from app.analysis.trade_planner import build_trade_plan
from app.analysis.valuation_blend import build_quick_buy_sell
from app.data import cache, yfinance_client
from app.database import db
from app.models.country import COUNTRY_REGISTRY
from app.models.stock import PricePoint
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


async def get_portfolio():
    """Get portfolio with current prices, risk context, and execution guidance."""
    cache_key = "portfolio_overview:v4"
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
