"""Short-horizon chart setup analysis for opportunity radar focus picks."""

from __future__ import annotations

import pandas as pd
from ta.trend import ADXIndicator, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

from app.models.market import ShortTermChartAnalysis, ShortTermChartFactor
from app.models.stock import PricePoint, TechnicalIndicators


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _last_value(values: list[float | None] | None) -> float | None:
    if not values:
        return None
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _factor_signal(score: float) -> str:
    if score >= 62.0:
        return "bullish"
    if score <= 42.0:
        return "bearish"
    return "neutral"


def _factor(key: str, label: str, score: float, detail: str) -> ShortTermChartFactor:
    normalized = round(_clip(score, 5.0, 95.0), 1)
    return ShortTermChartFactor(
        key=key,
        label=label,
        signal=_factor_signal(normalized),
        score=normalized,
        detail=detail,
    )


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current / previous - 1.0) * 100.0


def _safe_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return default
    if pd.isna(result):
        return default
    return result


def build_short_horizon_chart_analysis(
    *,
    price_history: list[PricePoint],
    technical: TechnicalIndicators,
    current_price: float,
) -> ShortTermChartAnalysis:
    if current_price <= 0 or len(price_history) < 25:
        return ShortTermChartAnalysis(
            score=50.0,
            signal="neutral",
            summary="차트 이력이 충분하지 않아 기본 점수로 유지합니다.",
            entry_style="balanced",
        )

    df = pd.DataFrame([point.model_dump() for point in price_history])
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    ema9 = _safe_float(EMAIndicator(close, window=min(9, len(close))).ema_indicator().iloc[-1], current_price)
    ema21 = _safe_float(EMAIndicator(close, window=min(21, len(close))).ema_indicator().iloc[-1], current_price)
    bands = BollingerBands(close, window=min(20, len(close)), window_dev=2)
    band_mid = _safe_float(bands.bollinger_mavg().iloc[-1], current_price)
    band_upper = _safe_float(bands.bollinger_hband().iloc[-1], current_price)
    band_lower = _safe_float(bands.bollinger_lband().iloc[-1], current_price)

    adx = 18.0
    if len(df) >= 20:
        try:
            adx = _safe_float(
                ADXIndicator(high, low, close, window=min(14, max(len(df) - 1, 2))).adx().iloc[-1],
                18.0,
            )
        except Exception:
            adx = 18.0

    atr_value = _safe_float(
        AverageTrueRange(high, low, close, window=min(14, max(len(df) - 1, 2))).average_true_range().iloc[-1],
        0.0,
    )
    atr_pct = atr_value / current_price * 100.0 if current_price > 0 else 0.0

    ma20 = _last_value(technical.ma_20) or band_mid
    ma60 = _last_value(technical.ma_60)
    rsi = _last_value(technical.rsi_14) or 50.0
    prev_rsi = _safe_float((technical.rsi_14 or [rsi, rsi])[-2], rsi) if len(technical.rsi_14 or []) >= 2 else rsi
    macd = _last_value(technical.macd) or 0.0
    macd_signal = _last_value(technical.macd_signal) or 0.0
    macd_hist = _last_value(technical.macd_hist) or 0.0
    prev_macd_hist = (
        _safe_float((technical.macd_hist or [macd_hist, macd_hist])[-2], macd_hist)
        if len(technical.macd_hist or []) >= 2
        else macd_hist
    )

    last_close = _safe_float(close.iloc[-1], current_price)
    prev_close = _safe_float(close.iloc[-2], last_close) if len(close) >= 2 else last_close
    last_volume = _safe_float(volume.iloc[-1], 0.0)
    avg_volume_20 = _safe_float(volume.tail(min(20, len(volume))).mean(), last_volume or 1.0)
    volume_ratio = last_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

    daily_return_pct = _pct_change(last_close, prev_close)
    return_3d_pct = _pct_change(last_close, _safe_float(close.iloc[-4], last_close)) if len(close) >= 4 else 0.0
    return_5d_pct = _pct_change(last_close, _safe_float(close.iloc[-6], last_close)) if len(close) >= 6 else 0.0
    high_20 = _safe_float(high.tail(min(20, len(high))).max(), current_price)
    distance_to_high_20_pct = max((high_20 / current_price - 1.0) * 100.0, 0.0) if current_price > 0 else 0.0
    distance_to_ema21_pct = (current_price / ema21 - 1.0) * 100.0 if ema21 > 0 else 0.0
    band_position = (
        (current_price - band_lower) / (band_upper - band_lower)
        if band_upper > band_lower
        else 0.5
    )
    upper_band_extension_pct = (current_price / band_upper - 1.0) * 100.0 if band_upper > 0 else 0.0

    trend_score = 50.0
    if current_price >= ema21:
        trend_score += 12.0
    else:
        trend_score -= 18.0
    if current_price >= ema9:
        trend_score += 6.0
    else:
        trend_score -= 8.0
    if ema9 >= ema21:
        trend_score += 12.0
    else:
        trend_score -= 14.0
    if ma60 is not None and ma20 is not None:
        trend_score += 8.0 if ma20 >= ma60 else -8.0
    if adx >= 24.0:
        trend_score += 10.0
    elif adx >= 18.0:
        trend_score += 4.0
    elif adx <= 14.0:
        trend_score -= 8.0
    trend_factor = _factor(
        "trend_alignment",
        "추세 정렬",
        trend_score,
        f"EMA9 {ema9:.2f}, EMA21 {ema21:.2f}, MA20 {ma20:.2f}, ADX {adx:.1f}",
    )

    momentum_score = 50.0
    momentum_score += 16.0 if macd >= macd_signal else -16.0
    momentum_score += 10.0 if macd_hist >= 0 else -10.0
    if macd_hist > prev_macd_hist:
        momentum_score += 8.0
    elif macd_hist < prev_macd_hist:
        momentum_score -= 8.0
    momentum_score += 6.0 if macd >= 0 else -6.0
    momentum_factor = _factor(
        "macd_momentum",
        "MACD 모멘텀",
        momentum_score,
        f"MACD {macd:.2f}, 시그널 {macd_signal:.2f}, 히스토그램 {macd_hist:.2f}",
    )

    rsi_score = 50.0
    if 52.0 <= rsi <= 68.0:
        rsi_score += 24.0
    elif 48.0 <= rsi < 52.0 or 68.0 < rsi <= 72.0:
        rsi_score += 10.0
    elif 72.0 < rsi <= 78.0:
        rsi_score -= 10.0
    elif rsi < 40.0:
        rsi_score -= 20.0
    elif rsi < 48.0:
        rsi_score -= 8.0
    if rsi > prev_rsi:
        rsi_score += 6.0
    elif rsi < prev_rsi:
        rsi_score -= 4.0
    rsi_factor = _factor(
        "rsi_balance",
        "RSI 위치",
        rsi_score,
        f"RSI14 {rsi:.1f}, 직전 {prev_rsi:.1f}",
    )

    volume_score = 50.0
    if volume_ratio >= 1.35 and daily_return_pct >= 0:
        volume_score += 24.0
    elif volume_ratio >= 1.1 and daily_return_pct >= 0:
        volume_score += 14.0
    elif volume_ratio < 0.8 and distance_to_high_20_pct <= 2.5:
        volume_score -= 12.0
    if daily_return_pct < 0 and volume_ratio >= 1.2:
        volume_score -= 12.0
    if distance_to_high_20_pct <= 1.5 and volume_ratio >= 1.15:
        volume_score += 10.0
    volume_factor = _factor(
        "volume_confirmation",
        "거래량 확인",
        volume_score,
        f"최근 거래량 {volume_ratio:.2f}배, 일간 수익률 {daily_return_pct:+.2f}%",
    )

    breakout_score = 50.0
    if current_price >= ema21 and distance_to_high_20_pct <= 2.5:
        breakout_score += 18.0
    elif current_price >= ema21 and abs(distance_to_ema21_pct) <= 2.4:
        breakout_score += 14.0
    elif current_price < ema21 * 0.99:
        breakout_score -= 18.0
    if distance_to_ema21_pct >= 5.5:
        breakout_score -= 18.0
    elif distance_to_ema21_pct >= 3.5:
        breakout_score -= 8.0
    if band_position >= 0.82 and upper_band_extension_pct <= 0.8 and volume_ratio >= 1.05:
        breakout_score += 8.0
    breakout_factor = _factor(
        "breakout_quality",
        "돌파/눌림 품질",
        breakout_score,
        f"20일 고점까지 {distance_to_high_20_pct:.2f}%, EMA21 이격 {distance_to_ema21_pct:+.2f}%",
    )

    discipline_score = 56.0
    if 1.2 <= atr_pct <= 4.2:
        discipline_score += 10.0
    elif atr_pct > 5.0:
        discipline_score -= 10.0
    if return_5d_pct >= 8.0:
        discipline_score -= 22.0
    elif return_5d_pct >= 5.0:
        discipline_score -= 10.0
    elif -1.5 <= return_3d_pct <= 3.5:
        discipline_score += 8.0
    if upper_band_extension_pct >= 1.2:
        discipline_score -= 14.0
    elif upper_band_extension_pct <= 0.2 and band_position >= 0.6:
        discipline_score += 6.0
    discipline_factor = _factor(
        "extension_discipline",
        "과열/변동성",
        discipline_score,
        f"5일 수익률 {return_5d_pct:+.2f}%, ATR {atr_pct:.2f}%, 밴드 상단 이격 {upper_band_extension_pct:+.2f}%",
    )

    weighted_score = (
        trend_factor.score * 0.24
        + momentum_factor.score * 0.18
        + rsi_factor.score * 0.12
        + volume_factor.score * 0.16
        + breakout_factor.score * 0.18
        + discipline_factor.score * 0.12
    )
    chart_score = round(_clip(weighted_score, 5.0, 95.0), 1)

    caution_flags: list[str] = []
    if rsi >= 72.0:
        caution_flags.append(f"RSI {rsi:.1f}로 단기 과열 구간에 가깝습니다.")
    if return_5d_pct >= 8.0:
        caution_flags.append(f"최근 5거래일 수익률이 {return_5d_pct:+.1f}%로 추격 매수 부담이 큽니다.")
    if upper_band_extension_pct >= 1.2:
        caution_flags.append("볼린저 상단을 강하게 이탈해 시가 추격보다 눌림 확인이 유리합니다.")
    if volume_ratio < 0.85 and distance_to_high_20_pct <= 2.5:
        caution_flags.append("고점 부근인데 거래량이 약해 돌파 신뢰도가 낮습니다.")
    if current_price < ema21 * 0.99:
        caution_flags.append("가격이 EMA21 아래로 밀려 단기 추세가 흔들리고 있습니다.")
    if adx <= 15.0:
        caution_flags.append("ADX가 낮아 방향성이 약합니다.")

    if chart_score < 45.0 or len(caution_flags) >= 3:
        entry_style = "stand_aside"
    elif distance_to_high_20_pct <= 1.5 and volume_ratio >= 1.1 and upper_band_extension_pct <= 0.8:
        entry_style = "breakout"
    elif current_price >= ema21 and abs(distance_to_ema21_pct) <= 2.4:
        entry_style = "pullback"
    else:
        entry_style = "balanced"

    signal = _factor_signal(chart_score)
    if signal == "bullish":
        opening = "단타 기준 차트 정렬이 비교적 잘 살아 있습니다."
    elif signal == "bearish":
        opening = "단타 기준 차트 정렬이 아직 불안정합니다."
    else:
        opening = "차트는 중립권이지만 일부 단기 신호는 확인됩니다."

    if entry_style == "breakout":
        style_note = "시가 추격보다는 거래량이 붙는 돌파 확인 뒤 대응이 맞습니다."
    elif entry_style == "pullback":
        style_note = "EMA21 안팎 눌림을 기다리는 진입이 더 유리합니다."
    elif entry_style == "stand_aside":
        style_note = "당일 추격보다 관망 또는 손절 우선 관리가 맞습니다."
    else:
        style_note = "돌파와 눌림 중 더 유리한 쪽을 장중 체결 흐름으로 구분해야 합니다."

    strongest = sorted(
        [trend_factor, momentum_factor, rsi_factor, volume_factor, breakout_factor, discipline_factor],
        key=lambda item: item.score,
        reverse=True,
    )[:2]
    weakness = min(
        [trend_factor, momentum_factor, rsi_factor, volume_factor, breakout_factor, discipline_factor],
        key=lambda item: item.score,
    )
    strength_labels = ", ".join(factor.label for factor in strongest)
    summary = f"{opening} 강한 축은 {strength_labels}이고, 가장 약한 축은 {weakness.label}입니다. {style_note}"

    return ShortTermChartAnalysis(
        score=chart_score,
        signal=signal,
        summary=summary,
        entry_style=entry_style,
        factors=[
            trend_factor,
            momentum_factor,
            rsi_factor,
            volume_factor,
            breakout_factor,
            discipline_factor,
        ],
        caution_flags=caution_flags[:4],
    )
