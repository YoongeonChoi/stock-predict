from __future__ import annotations

from math import log

import numpy as np
import pandas as pd

from .shared import clip, softmax


def to_frame(price_history: list[dict]) -> pd.DataFrame:
    if not price_history:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(price_history).copy()
    if "date" not in frame:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    for column in ("open", "high", "low", "close", "volume", "vwap"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = np.nan if column == "vwap" else 0.0
    return frame.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def return_series(close: pd.Series) -> np.ndarray:
    if close.empty:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(1)).dropna().to_numpy(dtype=float)


def horizon_returns(close: pd.Series, horizon: int) -> np.ndarray:
    if close.empty or len(close) <= horizon:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(horizon)).dropna().to_numpy(dtype=float)


def window_realized_vol(returns: np.ndarray, window: int) -> float:
    if len(returns) < 2:
        return 0.0
    clipped = returns[-window:] if len(returns) >= window else returns
    return float(np.std(clipped, ddof=1))


def garman_klass_vol(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    high = frame["high"].astype(float).replace(0, np.nan)
    low = frame["low"].astype(float).replace(0, np.nan)
    open_ = frame["open"].astype(float).replace(0, np.nan)
    close = frame["close"].astype(float).replace(0, np.nan)
    term = 0.5 * np.log(high / low) ** 2 - (2 * log(2) - 1) * np.log(close / open_) ** 2
    term = term.replace([np.inf, -np.inf], np.nan).dropna()
    if term.empty:
        return 0.0
    return float(np.sqrt(max(term.mean(), 0.0)))


def window_log_volume_z(volume: pd.Series, window: int) -> float:
    if volume.empty or len(volume) < 5:
        return 0.0
    clipped = np.log(np.maximum(volume.tail(window).to_numpy(dtype=float), 1.0))
    if len(clipped) < 2:
        return 0.0
    std = float(np.std(clipped, ddof=1))
    if std <= 1e-8:
        return 0.0
    return float((clipped[-1] - float(np.mean(clipped))) / std)


def proxy_vwap_gap(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    last = frame.iloc[-1]
    proxy = float(last.get("vwap") or 0.0)
    if proxy <= 0.0:
        typical = (
            (frame["high"].astype(float) + frame["low"].astype(float) + frame["close"].astype(float)) / 3.0
        ).tail(min(len(frame), 10))
        proxy = float(typical.mean()) if not typical.empty else float(last["close"])
    reference_price = float(last["close"])
    return (reference_price - proxy) / max(reference_price, 1e-6)


def log_return(close: pd.Series, window: int) -> float:
    if close.empty or len(close) <= 1:
        return 0.0
    usable = min(window, len(close) - 1)
    start = float(close.iloc[-usable - 1])
    end = float(close.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    return float(log(end / start))


def encode_price_block(
    *,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    macro: dict,
    events,
    asset_type: str,
    periods: tuple[int, ...],
) -> dict:
    close = prices["close"].astype(float)
    returns = return_series(close)
    volume = prices["volume"].astype(float) if "volume" in prices else pd.Series(np.zeros(len(prices)))
    benchmark_close = benchmark["close"].astype(float) if not benchmark.empty else pd.Series(dtype=float)
    reference_price = float(close.iloc[-1])
    long_vol = max(window_realized_vol(returns, min(120, len(returns))), 0.008 if asset_type == "index" else 0.012)

    period_rows: list[dict] = []
    for window in periods:
        usable = min(window, len(close) - 1)
        if usable < 12:
            continue
        momentum = log_return(close, usable)
        relative_strength = momentum - log_return(benchmark_close, usable) if len(benchmark_close) > usable else 0.0
        rv = window_realized_vol(returns, usable)
        gk = garman_klass_vol(prices.tail(usable))
        trend_gap = (reference_price / max(float(close.tail(usable).mean()), 1e-6)) - 1.0
        vwap_gap = proxy_vwap_gap(prices.tail(min(usable, 20)))
        volume_z = window_log_volume_z(volume, usable)
        stress = (rv / max(long_vol, 1e-6)) - 1.0
        score = (
            clip(momentum / 0.12) * 0.34
            + clip(relative_strength / 0.08) * 0.22
            + clip(trend_gap / 0.06) * 0.14
            + clip(vwap_gap / 0.03) * 0.08
            + clip(volume_z / 2.4) * 0.08
            - clip(stress / 1.3) * 0.10
            - clip((gk - rv) / max(rv, 1e-6) / 1.8) * 0.04
        )
        period_rows.append(
            {
                "window": usable,
                "score": float(score),
                "momentum": float(momentum),
                "relative_strength": float(relative_strength),
                "rv": float(rv),
                "detail": (
                    f"{usable}일 모멘텀 {momentum * 100:.2f}%, 상대강도 {relative_strength * 100:.2f}%, "
                    f"실현변동성 {rv * 100:.2f}%"
                ),
            }
        )

    event_heat = abs(events.sentiment) + abs(events.surprise) + events.uncertainty
    macro_persistence = float(macro["score"]) + float(macro["factors"].get("activity", 0.0)) * 0.4
    logits = []
    for row in period_rows:
        window = row["window"]
        logits.append(
            abs(row["score"]) * 0.75
            + (0.55 if window <= 60 else 0.0) * event_heat
            + (0.35 if window >= 120 else -0.05) * macro_persistence
            - (0.18 if window >= 120 and asset_type == "index" and event_heat > 1.0 else 0.0)
        )
    weights = softmax(np.array(logits, dtype=float))
    period_weights = {int(row["window"]): round(float(weight), 4) for row, weight in zip(period_rows, weights)}
    fused_score = sum(row["score"] * float(weight) for row, weight in zip(period_rows, weights))
    fused_vol = sum(row["rv"] * float(weight) for row, weight in zip(period_rows, weights))
    return {
        "period_rows": period_rows,
        "period_weights": period_weights,
        "fused_score": float(fused_score),
        "fused_vol": float(fused_vol),
        "long_vol": long_vol,
    }

