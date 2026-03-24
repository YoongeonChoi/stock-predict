"""High-level market radar and opportunity scanning."""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.trade_planner import build_trade_plan
from app.analysis.valuation_blend import build_quick_buy_sell
from app.analysis.stock_analyzer import _calc_technicals
from app.data import cache, yfinance_client
from app.data.universe_data import resolve_universe
from app.models.country import COUNTRY_REGISTRY
from app.models.market import OpportunityItem, OpportunityRadarResponse
from app.models.stock import PricePoint, TechnicalIndicators
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scenario_snapshot(forecast) -> dict:
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


async def get_market_opportunities(country_code: str, limit: int = 12) -> dict:
    country_code = country_code.upper()
    cache_key = f"opportunity_radar:v4:{country_code}:{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {
            "country_code": country_code,
            "generated_at": datetime.now().isoformat(),
            "market_regime": None,
            "total_scanned": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "opportunities": [],
        }

    primary_index = country.indices[0]
    index_history = await yfinance_client.get_price_history(primary_index.ticker, period="6mo")
    regime_forecast = forecast_next_day(
        ticker=primary_index.ticker,
        name=primary_index.name,
        country_code=country_code,
        price_history=index_history,
        asset_type="index",
    )
    market_regime = build_market_regime(
        country_code=country_code,
        name=primary_index.name,
        price_history=index_history,
        next_day_forecast=regime_forecast,
    )

    universe_selection = await resolve_universe(country_code)
    universe = universe_selection.sectors
    candidates: list[tuple[str, str]] = []
    for sector, tickers in universe.items():
        for ticker in tickers[:3]:
            candidates.append((sector, ticker))

    async def _scan(candidate: tuple[str, str]) -> OpportunityItem | None:
        sector, ticker = candidate
        snapshot = await yfinance_client.get_market_snapshot(ticker, period="6mo")
        if not snapshot.get("valid"):
            return None

        info, prices, analyst_raw = await asyncio.gather(
            yfinance_client.get_stock_info(ticker),
            yfinance_client.get_price_history(ticker, period="6mo"),
            yfinance_client.get_analyst_ratings(ticker),
        )
        current_price = float(info.get("current_price") or snapshot.get("current_price") or 0)
        if current_price <= 0 or len(prices) < 40:
            return None

        quant_score = score_stock(info, price_hist=prices, analyst_counts=analyst_raw)
        buy_sell = build_quick_buy_sell(info)
        technical: TechnicalIndicators = _calc_technicals(prices)
        forecast = forecast_next_day(
            ticker=ticker,
            name=info.get("name", ticker),
            country_code=country_code,
            price_history=prices,
            analyst_context={
                **analyst_raw,
                "target_mean": info.get("target_mean"),
                "target_median": info.get("target_median"),
                "target_high": info.get("target_high"),
                "target_low": info.get("target_low"),
            },
            context_bias=((quant_score.total - 50.0) / 50.0) + (0.18 if market_regime.stance == "risk_on" else -0.18 if market_regime.stance == "risk_off" else 0.0),
            asset_type="stock",
        )
        price_points = [PricePoint(**point) for point in prices]
        trade_plan = build_trade_plan(
            ticker=ticker,
            current_price=current_price,
            price_history=price_points,
            technical=technical,
            buy_sell_guide=buy_sell,
            next_day_forecast=forecast,
            market_regime=market_regime,
        )

        prev_close = float(info.get("prev_close") or current_price)
        change_pct = ((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0
        valuation_gap = ((buy_sell.fair_value / current_price) - 1.0) * 100.0 if current_price else 0.0
        opportunity_score = (
            quant_score.total * 0.34
            + max(forecast.up_probability - 50.0, 0.0) * 1.1
            + forecast.confidence * 0.18
            + min(max(trade_plan.risk_reward_estimate, 0.0), 4.0) * 6.0
            + (7.0 if market_regime.stance == "risk_on" else -3.0 if market_regime.stance == "risk_off" else 2.0)
            + (6.0 if current_price <= buy_sell.buy_zone_high * 1.02 else 1.5)
            + _clip(valuation_gap, -20.0, 20.0) * 0.18
        )
        execution_bias_bonus = {
            "press_long": 7.0,
            "lean_long": 4.0,
            "stay_selective": 1.0,
            "reduce_risk": -4.0,
            "capital_preservation": -8.0,
        }.get(forecast.execution_bias, 0.0)
        opportunity_score += execution_bias_bonus
        opportunity_score -= len(forecast.risk_flags[:2]) * 1.2
        opportunity_score = round(_clip(opportunity_score, 0.0, 100.0), 1)
        regime_tailwind = "tailwind" if market_regime.stance == "risk_on" else "headwind" if market_regime.stance == "risk_off" else "mixed"
        scenario_snapshot = _scenario_snapshot(forecast)

        return OpportunityItem(
            rank=0,
            ticker=ticker,
            name=info.get("name") or snapshot.get("name") or ticker,
            sector=sector,
            country_code=country_code,
            current_price=round(current_price, 2),
            change_pct=round(change_pct, 2),
            opportunity_score=opportunity_score,
            quant_score=round(quant_score.total, 1),
            up_probability=round(forecast.up_probability, 1),
            confidence=round(forecast.confidence, 1),
            predicted_return_pct=round(forecast.predicted_return_pct, 2),
            bull_case_price=scenario_snapshot["bull_case_price"],
            base_case_price=scenario_snapshot["base_case_price"],
            bear_case_price=scenario_snapshot["bear_case_price"],
            bull_probability=scenario_snapshot["bull_probability"],
            base_probability=scenario_snapshot["base_probability"],
            bear_probability=scenario_snapshot["bear_probability"],
            setup_label=trade_plan.setup_label,
            action=trade_plan.action,
            execution_bias=forecast.execution_bias,
            execution_note=forecast.execution_note,
            regime_tailwind=regime_tailwind,
            entry_low=trade_plan.entry_low,
            entry_high=trade_plan.entry_high,
            stop_loss=trade_plan.stop_loss,
            take_profit_1=trade_plan.take_profit_1,
            take_profit_2=trade_plan.take_profit_2,
            risk_reward_estimate=trade_plan.risk_reward_estimate,
            thesis=trade_plan.thesis[:2],
            risk_flags=forecast.risk_flags[:2],
            forecast_date=forecast.target_date,
        )

    scanned = await gather_limited(candidates, _scan, limit=6)
    opportunities = [item for item in scanned if not isinstance(item, Exception) and item is not None]
    opportunities.sort(key=lambda item: item.opportunity_score, reverse=True)

    ranked = []
    for idx, item in enumerate(opportunities[:limit], start=1):
        ranked.append(item.model_copy(update={"rank": idx}))

    response = OpportunityRadarResponse(
        country_code=country_code,
        generated_at=datetime.now().isoformat(),
        market_regime=market_regime,
        total_scanned=len(candidates),
        actionable_count=sum(1 for item in ranked if item.action in {"accumulate", "breakout_watch"}),
        bullish_count=sum(1 for item in ranked if item.up_probability >= 55),
        universe_source=universe_selection.source,
        universe_note=universe_selection.note,
        opportunities=ranked,
    ).model_dump()
    await cache.set(cache_key, response, 900)
    return response
