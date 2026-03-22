"""Market regime classification for countries and benchmark indices."""

from __future__ import annotations

from math import isnan

import numpy as np
import pandas as pd
from ta.trend import SMAIndicator

from app.models.forecast import FearGreedIndex, NextDayForecast
from app.models.market import MarketRegime, MarketRegimeSignal


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(series: pd.Series, periods: int) -> float:
    if len(series) <= periods:
        return 0.0
    start = float(series.iloc[-periods - 1])
    end = float(series.iloc[-1])
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def _signal(name: str, value: float, detail: str) -> MarketRegimeSignal:
    sentiment = "neutral"
    if value > 0.1:
        sentiment = "bullish"
    elif value < -0.1:
        sentiment = "bearish"
    return MarketRegimeSignal(
        name=name,
        value=round(value, 3),
        signal=sentiment,
        detail=detail,
    )


def _volatility_bucket(volatility_pct: float) -> str:
    if volatility_pct < 0.9:
        return "low"
    if volatility_pct > 1.8:
        return "high"
    return "normal"


def build_market_regime(
    *,
    country_code: str,
    name: str,
    price_history: list[dict],
    fear_greed: FearGreedIndex | None = None,
    next_day_forecast: NextDayForecast | None = None,
    economic_data: dict | None = None,
    breadth_ratio: float | None = None,
) -> MarketRegime:
    if not price_history or len(price_history) < 30:
        return MarketRegime(
            label=f"{name} Neutral Regime",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=50.0,
            conviction=35.0,
            summary=f"Not enough history to classify {name} decisively.",
            playbook=["Wait for stronger trend confirmation before increasing size."],
            warnings=["Market history was insufficient, so regime signals are low-conviction."],
            signals=[],
        )

    df = pd.DataFrame(price_history).sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)
    returns = np.log(close / close.shift(1)).dropna()
    current = float(close.iloc[-1])
    sma20 = float(SMAIndicator(close, window=min(20, len(close))).sma_indicator().iloc[-1])
    sma60 = float(SMAIndicator(close, window=min(60, len(close))).sma_indicator().iloc[-1])

    trend_1m = _pct_change(close, min(20, len(close) - 1))
    trend_3m = _pct_change(close, min(60, len(close) - 1))
    distance_20 = ((current / sma20) - 1.0) * 100 if sma20 else 0.0
    distance_60 = ((current / sma60) - 1.0) * 100 if sma60 else 0.0
    volatility_20 = float(returns.tail(20).std() * 100) if len(returns) >= 20 else float(returns.std() * 100)
    if isnan(volatility_20):
        volatility_20 = 0.0
    recent_high = float(close.tail(60).max()) if len(close) >= 60 else float(close.max())
    drawdown = ((current / recent_high) - 1.0) * 100 if recent_high else 0.0

    trend_signal = _clip((trend_1m * 0.65 + trend_3m * 0.35) / 8.0, -1.0, 1.0)
    structure_signal = _clip((distance_20 * 0.6 + distance_60 * 0.4) / 4.0, -1.0, 1.0)
    volatility_signal = _clip((1.4 - volatility_20) / 1.4, -1.0, 1.0)
    drawdown_signal = _clip((drawdown + 7.0) / 7.0, -1.0, 1.0)

    fear_signal = 0.0
    if fear_greed:
        fear_signal = _clip((fear_greed.score - 50.0) / 35.0, -1.0, 1.0)

    breadth_signal = _clip((((breadth_ratio or 0.5) - 0.5) * 2.0), -1.0, 1.0)

    forecast_signal = 0.0
    if next_day_forecast:
        forecast_signal = _clip((next_day_forecast.up_probability - 50.0) / 35.0, -1.0, 1.0)

    macro_signal = 0.0
    macro_details: list[str] = []
    economic_data = economic_data or {}
    treasury_spread = economic_data.get("treasury_spread")
    if treasury_spread is not None:
        macro_signal += 0.35 if treasury_spread > 0 else -0.35
        macro_details.append(f"2s10s spread {treasury_spread:.2f}.")
    vix_value = economic_data.get("vix")
    if vix_value is not None:
        macro_signal += _clip((20.0 - float(vix_value)) / 20.0, -0.4, 0.4)
        macro_details.append(f"VIX {float(vix_value):.1f}.")
    macro_signal = _clip(macro_signal, -1.0, 1.0)

    composite = (
        trend_signal * 0.26
        + structure_signal * 0.18
        + volatility_signal * 0.14
        + drawdown_signal * 0.10
        + fear_signal * 0.12
        + forecast_signal * 0.10
        + breadth_signal * 0.06
        + macro_signal * 0.04
    )
    score = round((_clip(composite, -1.0, 1.0) + 1.0) * 50.0, 1)
    conviction = round(_clip(38.0 + abs(composite) * 44.0 + min(abs(trend_1m), 8.0) * 1.5, 35.0, 92.0), 1)

    if trend_signal > 0.2 and current >= sma60:
        trend = "uptrend"
    elif trend_signal < -0.2 and current < sma60:
        trend = "downtrend"
    else:
        trend = "range"

    volatility = _volatility_bucket(volatility_20)
    if breadth_signal > 0.2:
        breadth = "strong"
    elif breadth_signal < -0.2:
        breadth = "weak"
    else:
        breadth = "mixed"

    if composite >= 0.28 and volatility == "high":
        label = "High-Volatility Advance"
        stance = "risk_on"
    elif composite >= 0.22:
        label = "Risk-On Trend"
        stance = "risk_on"
    elif composite <= -0.32 and volatility == "high":
        label = "Risk-Off Breakdown"
        stance = "risk_off"
    elif composite <= -0.2:
        label = "Defensive Pullback"
        stance = "risk_off"
    elif trend == "downtrend":
        label = "Fragile Bounce"
        stance = "neutral"
    else:
        label = "Rangebound Rotation"
        stance = "neutral"

    playbook_map = {
        "risk_on": [
            "Buy controlled pullbacks that hold above the 20-day average.",
            "Favor relative-strength leaders over deep laggards.",
            "Let winners run into target zones instead of taking profits too early.",
        ],
        "neutral": [
            "Scale into positions instead of going full size immediately.",
            "Prefer fast profit-taking near resistance and tighter stop management.",
            "Wait for confirmation before chasing extended moves.",
        ],
        "risk_off": [
            "Cut position size and keep stops tighter than usual.",
            "Prefer cash, hedges, or defensive sectors over aggressive rotation.",
            "Treat rallies as suspect until breadth and trend structure improve.",
        ],
    }

    warnings: list[str] = []
    if volatility == "high":
        warnings.append("Realized volatility is elevated, so intraday swings can overwhelm weak setups.")
    if fear_greed and fear_greed.score >= 75:
        warnings.append("Sentiment is overheated; breakout follow-through can become fragile.")
    if fear_greed and fear_greed.score <= 25:
        warnings.append("Sentiment is stressed; expect headline sensitivity and fast reversals.")
    if treasury_spread is not None and treasury_spread < 0:
        warnings.append("The yield curve is inverted, which is a macro headwind for broad risk appetite.")
    if next_day_forecast and next_day_forecast.up_probability < 45:
        warnings.append("Short-horizon model odds are not supportive right now.")

    summary = (
        f"{name} is in a {label.lower()} regime: {trend} structure, {volatility} volatility, "
        f"and {breadth} breadth. Composite regime score is {score:.1f}/100."
    )

    signals = [
        _signal("Trend", trend_signal, f"1M {trend_1m:.2f}% / 3M {trend_3m:.2f}%."),
        _signal("Structure", structure_signal, f"Vs SMA20 {distance_20:.2f}% / SMA60 {distance_60:.2f}%."),
        _signal("Volatility", volatility_signal, f"20-day realized volatility {volatility_20:.2f}%."),
        _signal("Drawdown", drawdown_signal, f"Distance from 3M high {drawdown:.2f}%."),
        _signal("Sentiment", fear_signal, f"Fear & Greed {fear_greed.score:.1f}." if fear_greed else "No sentiment overlay."),
        _signal("Short Horizon", forecast_signal, f"Up probability {next_day_forecast.up_probability:.1f}%." if next_day_forecast else "No next-day overlay."),
        _signal("Breadth", breadth_signal, f"Breadth proxy {breadth_ratio:.2f}." if breadth_ratio is not None else "Breadth proxy neutral."),
        _signal("Macro", macro_signal, " ".join(macro_details) if macro_details else "No macro overlay."),
    ]

    return MarketRegime(
        label=label,
        stance=stance,
        trend=trend,
        volatility=volatility,
        breadth=breadth,
        score=score,
        conviction=conviction,
        summary=summary,
        playbook=playbook_map[stance],
        warnings=warnings,
        signals=signals,
    )
