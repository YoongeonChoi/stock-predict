"""Deterministic trade plan builder."""

from __future__ import annotations

import pandas as pd
from ta.volatility import AverageTrueRange

from app.models.forecast import NextDayForecast
from app.models.market import MarketRegime, TradePlan
from app.models.stock import BuySellGuide, PricePoint, TechnicalIndicators


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _last_value(values: list[float | None] | None) -> float | None:
    if not values:
        return None
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _atr_pct(price_history: list[PricePoint], current_price: float) -> float:
    if len(price_history) < 14 or current_price <= 0:
        return 2.2
    df = pd.DataFrame([point.model_dump() for point in price_history])
    atr = AverageTrueRange(
        df["high"].astype(float),
        df["low"].astype(float),
        df["close"].astype(float),
        window=min(14, len(df) - 1),
    ).average_true_range()
    return max(float(atr.iloc[-1]) / current_price * 100.0, 1.2)


def build_trade_plan(
    *,
    ticker: str,
    current_price: float,
    price_history: list[PricePoint],
    technical: TechnicalIndicators,
    buy_sell_guide: BuySellGuide,
    next_day_forecast: NextDayForecast | None,
    market_regime: MarketRegime | None = None,
) -> TradePlan:
    if current_price <= 0:
        return TradePlan(
            setup_label=f"{ticker} Observation Only",
            action="avoid",
            conviction=30.0,
            thesis=["Price data is incomplete, so execution planning is disabled."],
            invalidation="Refresh the dataset before acting on this name.",
        )

    ma20 = _last_value(technical.ma_20)
    ma60 = _last_value(technical.ma_60)
    rsi = _last_value(technical.rsi_14) or 50.0
    macd_hist = _last_value(technical.macd_hist) or 0.0
    atr_pct = _atr_pct(price_history, current_price)

    regime_tailwind = 0.0
    if market_regime:
        regime_tailwind = 0.18 if market_regime.stance == "risk_on" else -0.18 if market_regime.stance == "risk_off" else 0.0

    bullish_forecast = bool(next_day_forecast and next_day_forecast.up_probability >= 58 and next_day_forecast.direction != "down")
    bearish_forecast = bool(next_day_forecast and (next_day_forecast.up_probability <= 42 or next_day_forecast.direction == "down"))
    near_buy_zone = current_price <= buy_sell_guide.buy_zone_high * 1.02
    premium_to_fair = current_price >= buy_sell_guide.fair_value * 1.05
    trend_confirmed = bool(ma20 and current_price > ma20 and (ma60 is None or current_price >= ma60))

    if bullish_forecast and near_buy_zone and not premium_to_fair:
        setup_label = "Pullback Accumulation"
        action = "accumulate"
        entry_low = max(buy_sell_guide.buy_zone_low, current_price * 0.985)
        entry_high = min(buy_sell_guide.buy_zone_high, current_price * 1.01)
        hold_days = 8
    elif bullish_forecast and trend_confirmed and macd_hist >= 0:
        setup_label = "Momentum Continuation"
        action = "breakout_watch"
        entry_low = current_price * 0.995
        entry_high = current_price * 1.02
        hold_days = 5
    elif rsi < 38 and next_day_forecast and next_day_forecast.up_probability >= 55:
        setup_label = "Mean-Reversion Swing"
        action = "accumulate"
        entry_low = max(buy_sell_guide.buy_zone_low, current_price * 0.98)
        entry_high = min(current_price * 1.005, buy_sell_guide.buy_zone_high * 1.02)
        hold_days = 6
    elif bearish_forecast or (market_regime and market_regime.stance == "risk_off" and premium_to_fair):
        setup_label = "Risk Reduction"
        action = "reduce_risk"
        entry_low = None
        entry_high = None
        hold_days = 3
    else:
        setup_label = "Wait For Confirmation"
        action = "wait_pullback"
        entry_low = buy_sell_guide.buy_zone_low
        entry_high = min(buy_sell_guide.buy_zone_high, current_price * 0.99)
        hold_days = 5

    stop_loss = None
    take_profit_1 = None
    take_profit_2 = None
    if entry_low is not None:
        risk_buffer = max(atr_pct * 1.25, 4.0)
        stop_loss = entry_low * (1.0 - risk_buffer / 100.0)
        take_profit_1 = max(
            buy_sell_guide.fair_value,
            current_price * (1.0 + max((next_day_forecast.predicted_return_pct if next_day_forecast else 0.0), 1.8) / 100.0),
        )
        take_profit_2 = max(buy_sell_guide.sell_zone_low, buy_sell_guide.sell_zone_high * 0.97, take_profit_1 * 1.04)
    elif action == "reduce_risk":
        stop_loss = current_price * (1.0 - max(atr_pct * 0.8, 2.8) / 100.0)
        take_profit_1 = buy_sell_guide.sell_zone_low or current_price * 1.03
        take_profit_2 = buy_sell_guide.sell_zone_high or current_price * 1.06

    entry_reference = (entry_low + entry_high) / 2.0 if entry_low is not None and entry_high is not None else current_price
    risk_reward = 0.0
    if stop_loss and take_profit_1 and entry_reference > stop_loss:
        risk_reward = max((take_profit_1 - entry_reference) / (entry_reference - stop_loss), 0.0)

    thesis = []
    if next_day_forecast:
        thesis.append(
            f"Short-horizon model points to {next_day_forecast.direction} with {next_day_forecast.up_probability:.1f}% upside odds into {next_day_forecast.target_date}."
        )
    thesis.append(
        f"Current price is {((current_price / buy_sell_guide.fair_value) - 1.0) * 100:+.1f}% versus fair value."
        if buy_sell_guide.fair_value
        else "Fair value estimate is neutral, so execution should stay size-aware."
    )
    if market_regime:
        tailwind = "tailwind" if market_regime.stance == "risk_on" else "headwind" if market_regime.stance == "risk_off" else "mixed tape"
        thesis.append(f"Market regime is {market_regime.label.lower()}, which creates a {tailwind} for this setup.")
    else:
        thesis.append("Market regime context is limited, so execution should stay flexible.")

    invalidation = "A daily close below the proposed stop loss invalidates the setup."
    if action == "reduce_risk":
        invalidation = "If price reclaims the 20-day structure with rising forecast odds, reassess the defensive posture."
    elif action == "wait_pullback":
        invalidation = "If price extends without resetting into the entry band, do not chase; wait for a cleaner pullback."

    conviction = 42.0
    if next_day_forecast:
        conviction += next_day_forecast.confidence * 0.45
    if market_regime:
        conviction += market_regime.conviction * 0.22 * (1 if regime_tailwind >= 0 else -0.5)
    conviction += min(risk_reward, 4.0) * 4.0
    conviction = round(_clip(conviction, 28.0, 94.0), 1)

    return TradePlan(
        setup_label=setup_label,
        action=action,
        conviction=conviction,
        entry_low=round(entry_low, 2) if entry_low is not None else None,
        entry_high=round(entry_high, 2) if entry_high is not None else None,
        stop_loss=round(stop_loss, 2) if stop_loss is not None else None,
        take_profit_1=round(take_profit_1, 2) if take_profit_1 is not None else None,
        take_profit_2=round(take_profit_2, 2) if take_profit_2 is not None else None,
        expected_holding_days=hold_days,
        risk_reward_estimate=round(risk_reward, 2),
        thesis=thesis,
        invalidation=invalidation,
    )
