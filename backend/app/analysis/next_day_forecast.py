"""Deterministic next-trading-day forecast engine."""

from __future__ import annotations

from datetime import datetime
from math import exp

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange

from app.models.forecast import FlowSignal, ForecastDriver, NextDayForecast
from app.utils.market_calendar import next_trading_day

MODEL_VERSION = "signal-v2.1"

POSITIVE_NEWS = {
    "beat", "beats", "bullish", "buyback", "eases", "expansion", "gain", "gains",
    "growth", "improves", "inflow", "innovation", "optimistic", "outperform",
    "rally", "rebound", "record", "resilient", "rise", "rises", "strong",
    "surge", "surges", "upgrade", "upside",
}
NEGATIVE_NEWS = {
    "bearish", "cut", "cuts", "decline", "declines", "downgrade", "drop", "drops",
    "fear", "fraud", "inflation", "miss", "misses", "outflow", "probe", "recession",
    "risk", "risks", "selloff", "slump", "slowdown", "tariff", "underperform",
    "volatility", "warning", "warnings", "weak",
}


def _clip(value: float, floor: float, ceiling: float) -> float:
    return max(floor, min(ceiling, value))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _pct_change(series: pd.Series, periods: int) -> float:
    if len(series) <= periods:
        return 0.0
    start = float(series.iloc[-periods - 1])
    end = float(series.iloc[-1])
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def _flow_score(flow_signal: FlowSignal | None) -> tuple[float | None, str]:
    if not flow_signal or not flow_signal.available:
        return None, "No verified investor flow data."

    foreign = flow_signal.foreign_net_buy or 0.0
    institutional = flow_signal.institutional_net_buy or 0.0
    retail = flow_signal.retail_net_buy or 0.0
    denominator = abs(foreign) + abs(institutional) + abs(retail)
    if denominator <= 0:
        return 0.0, "Investor flow was directionally mixed."

    score = _clip((foreign + institutional * 0.7 - retail * 0.3) / denominator, -1.0, 1.0)
    detail = (
        f"Foreign {foreign:,.0f} {flow_signal.unit}, institution {institutional:,.0f}, "
        f"retail {retail:,.0f} over the latest session window."
    )
    return score, detail


def _analyst_score(analyst_context: dict | None, current_price: float) -> tuple[float | None, str]:
    if not analyst_context:
        return None, "No analyst context."

    target_mean = analyst_context.get("target_mean")
    buy = float(analyst_context.get("buy", 0) or 0)
    hold = float(analyst_context.get("hold", 0) or 0)
    sell = float(analyst_context.get("sell", 0) or 0)

    score_parts: list[float] = []
    details: list[str] = []

    if target_mean and current_price:
        target_gap = (float(target_mean) / current_price - 1.0) * 100.0
        score_parts.append(_clip(target_gap / 15.0, -1.0, 1.0))
        details.append(f"Target mean gap {target_gap:.2f}%.")

    consensus_total = buy + hold + sell
    if consensus_total > 0:
        consensus_score = (buy - sell) / consensus_total
        score_parts.append(_clip(consensus_score, -1.0, 1.0))
        details.append(f"Consensus {buy:.0f} buy / {hold:.0f} hold / {sell:.0f} sell.")

    if not score_parts:
        return None, "No analyst target or recommendation counts."
    return float(np.mean(score_parts)), " ".join(details)


def _news_sentiment(news_items: list[dict] | None) -> tuple[float, str]:
    if not news_items:
        return 0.0, "No relevant headlines."

    scores = []
    for item in news_items[:12]:
        title = str(item.get("title", "")).lower()
        if not title:
            continue
        positive_hits = sum(1 for word in POSITIVE_NEWS if word in title)
        negative_hits = sum(1 for word in NEGATIVE_NEWS if word in title)
        if positive_hits == negative_hits == 0:
            scores.append(0.0)
            continue
        scores.append(_clip((positive_hits - negative_hits) / 2.0, -1.0, 1.0))

    if not scores:
        return 0.0, "Headlines were neutral."

    sentiment = float(np.mean(scores))
    return sentiment, f"Headline sentiment score {sentiment:.2f} across {len(scores)} items."


def _build_driver(
    name: str,
    value: float,
    weight: float,
    detail: str,
) -> ForecastDriver:
    signal = "neutral"
    if value > 0.05:
        signal = "bullish"
    elif value < -0.05:
        signal = "bearish"
    return ForecastDriver(
        name=name,
        value=round(value, 3),
        signal=signal,
        weight=round(weight, 3),
        contribution=round(weight * value, 3),
        detail=detail,
    )


def _fallback_forecast(
    ticker: str,
    country_code: str,
    current_price: float,
    reference_date: str,
) -> NextDayForecast:
    target_date = next_trading_day(country_code, reference_date).isoformat()
    return NextDayForecast(
        target_date=target_date,
        reference_date=reference_date,
        reference_price=round(current_price, 2),
        direction="flat",
        up_probability=50.0,
        predicted_open=round(current_price, 2) if current_price else None,
        predicted_close=round(current_price, 2),
        predicted_high=round(current_price * 1.01, 2),
        predicted_low=round(current_price * 0.99, 2),
        predicted_return_pct=0.0,
        confidence=30.0,
        confidence_note=f"Insufficient market history for {ticker}; using neutral fallback.",
        news_sentiment=0.0,
        raw_signal=0.0,
        flow_signal=None,
        drivers=[],
        model_version=MODEL_VERSION,
    )


def forecast_next_day(
    *,
    ticker: str,
    name: str,
    country_code: str,
    price_history: list[dict],
    news_items: list[dict] | None = None,
    analyst_context: dict | None = None,
    flow_signal: FlowSignal | None = None,
    context_bias: float | None = None,
    asset_type: str = "stock",
) -> NextDayForecast:
    if not price_history:
        return _fallback_forecast(ticker, country_code, 0.0, datetime.now().date().isoformat())

    df = pd.DataFrame(price_history).copy()
    if df.empty or len(df) < 25:
        last_close = float(df["close"].iloc[-1]) if not df.empty else 0.0
        reference_date = str(df["date"].iloc[-1]) if not df.empty else datetime.now().date().isoformat()
        return _fallback_forecast(ticker, country_code, last_close, reference_date)

    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    current_price = float(close.iloc[-1])
    reference_date = str(df["date"].iloc[-1])
    target_date = next_trading_day(country_code, reference_date).isoformat()

    returns = np.log(close / close.shift(1)).dropna()
    daily_vol_pct = max(float(returns.tail(20).std() * 100), 0.35)
    drift_pct = float(returns.tail(20).mean() * 100)

    ema_fast = EMAIndicator(close, window=min(10, len(close))).ema_indicator()
    ema_slow = EMAIndicator(close, window=min(21, len(close))).ema_indicator()
    rsi = RSIIndicator(close, window=min(14, len(close) - 1)).rsi()
    macd = MACD(close, window_fast=min(12, len(close) - 1), window_slow=min(26, len(close)), window_sign=min(9, len(close) - 1))
    atr = AverageTrueRange(high, low, close, window=min(14, len(close) - 1)).average_true_range()

    trend_5d = _pct_change(close, 5)
    trend_21d = _pct_change(close, 21)
    reversal_1d = -_pct_change(close, 1)
    ema_gap_pct = ((float(ema_fast.iloc[-1]) - float(ema_slow.iloc[-1])) / current_price * 100) if current_price else 0.0
    rsi_last = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
    macd_hist_last = float(macd.macd_diff().iloc[-1]) if pd.notna(macd.macd_diff().iloc[-1]) else 0.0
    atr_pct = (float(atr.iloc[-1]) / current_price * 100.0) if current_price and pd.notna(atr.iloc[-1]) else daily_vol_pct

    volume_avg = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
    volume_std = float(volume.tail(20).std()) if len(volume) >= 20 else float(volume.std())
    volume_z = (float(volume.iloc[-1]) - volume_avg) / max(volume_std, volume_avg * 0.15, 1.0)

    momentum_score = _clip((trend_5d * 0.7 + trend_21d * 0.3) / max(daily_vol_pct * 2.0, 0.8), -1.2, 1.2)
    ema_score = _clip(ema_gap_pct / max(daily_vol_pct, 0.6), -1.0, 1.0)
    rsi_score = _clip((50.0 - rsi_last) / 20.0, -1.0, 1.0)
    macd_score = _clip(macd_hist_last / max(current_price * 0.002, 0.01), -1.0, 1.0)
    volume_score = _clip((volume_z / 2.0) * np.sign(trend_5d or reversal_1d), -1.0, 1.0)

    analyst_score, analyst_detail = _analyst_score(analyst_context, current_price)
    news_score, news_detail = _news_sentiment(news_items)
    flow_score, flow_detail = _flow_score(flow_signal)
    context_score = _clip(float(context_bias or 0.0), -1.0, 1.0)
    volatility_penalty = _clip((atr_pct / max(daily_vol_pct, 0.5)) - 1.0, 0.0, 1.2)

    available_drivers = [
        ("Momentum", momentum_score, 0.21, f"5-day {trend_5d:.2f}%, 1-month {trend_21d:.2f}%."),
        ("EMA Trend", ema_score, 0.15, f"EMA(10)-EMA(21) gap {ema_gap_pct:.2f}%."),
        ("RSI Mean Reversion", rsi_score, 0.10, f"RSI(14) at {rsi_last:.2f}."),
        ("MACD Impulse", macd_score, 0.12, f"MACD histogram {macd_hist_last:.4f}."),
        ("Volume Confirmation", volume_score, 0.07, f"Volume z-score {volume_z:.2f}."),
        ("News Sentiment", news_score, 0.13, news_detail),
        ("Context Bias", context_score, 0.08, f"Context bias {context_score:.2f}."),
    ]

    if analyst_score is not None:
        available_drivers.append(("Analyst Skew", analyst_score, 0.10, analyst_detail))
    if flow_score is not None:
        available_drivers.append(("Investor Flow", flow_score, 0.14, flow_detail))

    total_weight = sum(weight for _, _, weight, _ in available_drivers) or 1.0
    drivers = [
        _build_driver(name, value, weight / total_weight, detail)
        for name, value, weight, detail in available_drivers
    ]
    signal_strength = float(sum(driver.contribution for driver in drivers))

    scale = 0.85 if asset_type == "index" else 1.0
    expected_return_pct = drift_pct * 0.35 + signal_strength * max(daily_vol_pct * 0.95 * scale, 0.45)
    expected_return_pct *= 1.0 - (volatility_penalty * 0.18)
    expected_return_pct = _clip(expected_return_pct, -3.8 if asset_type == "index" else -5.0, 3.8 if asset_type == "index" else 5.0)

    up_probability = _clip(
        _sigmoid(signal_strength * 3.4 + expected_return_pct / max(daily_vol_pct, 0.55)) * 100.0,
        5.0,
        95.0,
    )

    predicted_open = current_price * (1.0 + expected_return_pct * 0.35 / 100.0)
    predicted_close = current_price * (1.0 + expected_return_pct / 100.0)
    intraday_range_pct = max(atr_pct * 0.85, daily_vol_pct * 0.8, 0.45 if asset_type == "index" else 0.7)
    band_factor = 0.55 + min(abs(expected_return_pct) / 4.0, 0.25)
    predicted_high = max(predicted_open, predicted_close) * (1.0 + intraday_range_pct * band_factor / 100.0)
    predicted_low = min(predicted_open, predicted_close) * (1.0 - intraday_range_pct * band_factor / 100.0)

    if abs(expected_return_pct) < 0.12:
        direction = "flat"
    else:
        direction = "up" if expected_return_pct > 0 else "down"

    coverage = len(drivers) / 9.0
    confidence = 48.0 + abs(signal_strength) * 24.0 + coverage * 12.0 - volatility_penalty * 10.0
    confidence = _clip(confidence, 35.0, 92.0)

    note_parts = [
        f"{name} next-day model for {ticker}.",
        f"Realized 20-day volatility {daily_vol_pct:.2f}% and ATR {atr_pct:.2f}%.",
    ]
    if flow_signal and not flow_signal.available:
        note_parts.append("Investor flow data was unavailable, so flow weight was neutralized.")

    ranked_drivers = sorted(drivers, key=lambda item: abs(item.contribution), reverse=True)[:5]

    return NextDayForecast(
        target_date=target_date,
        reference_date=reference_date,
        reference_price=round(current_price, 2),
        direction=direction,
        up_probability=round(up_probability, 2),
        predicted_open=round(predicted_open, 2),
        predicted_close=round(predicted_close, 2),
        predicted_high=round(predicted_high, 2),
        predicted_low=round(predicted_low, 2),
        predicted_return_pct=round(expected_return_pct, 2),
        confidence=round(confidence, 2),
        confidence_note=" ".join(note_parts),
        news_sentiment=round(news_score, 3),
        raw_signal=round(signal_strength, 3),
        flow_signal=flow_signal,
        drivers=ranked_drivers,
        model_version=MODEL_VERSION,
    )
