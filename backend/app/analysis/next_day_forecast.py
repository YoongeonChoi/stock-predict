"""Deterministic next-trading-day forecast engine."""

from __future__ import annotations

from datetime import datetime
from math import exp

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange

from app.models.forecast import FlowSignal, ForecastDriver, ForecastScenario, NextDayForecast
from app.utils.market_calendar import next_trading_day

MODEL_VERSION = "signal-v2.4"

POSITIVE_NEWS = {
    "beat": 0.8,
    "beats": 0.8,
    "bullish": 0.6,
    "buyback": 0.7,
    "eases": 0.45,
    "expansion": 0.45,
    "gain": 0.35,
    "gains": 0.35,
    "growth": 0.45,
    "improves": 0.45,
    "inflow": 0.55,
    "innovation": 0.4,
    "optimistic": 0.5,
    "outperform": 0.65,
    "rally": 0.55,
    "rebound": 0.45,
    "record": 0.5,
    "resilient": 0.55,
    "rise": 0.3,
    "rises": 0.3,
    "strong": 0.45,
    "surge": 0.55,
    "surges": 0.55,
    "upgrade": 0.75,
    "upside": 0.45,
    "상향": 0.75,
    "호조": 0.65,
    "반등": 0.55,
    "개선": 0.45,
    "증가": 0.35,
    "회복": 0.55,
    "흑자": 0.7,
    "최대": 0.4,
    "서프라이즈": 0.8,
    "강세": 0.55,
    "매수": 0.5,
}
NEGATIVE_NEWS = {
    "bearish": 0.6,
    "cut": 0.55,
    "cuts": 0.55,
    "decline": 0.45,
    "declines": 0.45,
    "downgrade": 0.75,
    "drop": 0.45,
    "drops": 0.45,
    "fear": 0.5,
    "fraud": 0.95,
    "inflation": 0.4,
    "miss": 0.75,
    "misses": 0.75,
    "outflow": 0.6,
    "probe": 0.6,
    "recession": 0.7,
    "risk": 0.35,
    "risks": 0.35,
    "selloff": 0.7,
    "slump": 0.65,
    "slowdown": 0.55,
    "tariff": 0.4,
    "underperform": 0.7,
    "volatility": 0.25,
    "warning": 0.7,
    "warnings": 0.7,
    "weak": 0.55,
    "하향": 0.75,
    "부진": 0.7,
    "둔화": 0.55,
    "악화": 0.65,
    "감소": 0.4,
    "적자": 0.75,
    "급락": 0.8,
    "경고": 0.7,
    "매도": 0.55,
    "쇼크": 0.75,
}
TRUSTED_SOURCES = {"reuters", "bloomberg", "wsj", "marketwatch", "cnbc", "연합뉴스", "매일경제", "한국경제"}


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


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _headline_relevance(title: str, ticker: str, name: str) -> float:
    relevance = 1.0
    lower = title.lower()
    if ticker.lower() in lower:
        relevance += 0.1
    tokens = [token.lower() for token in str(name).split() if len(token) >= 4]
    if any(token in lower for token in tokens[:2]):
        relevance += 0.08
    return relevance


def _flow_score(flow_signal: FlowSignal | None) -> tuple[float | None, str]:
    if not flow_signal or not flow_signal.available:
        return None, "검증된 외국인/기관 수급 데이터가 없어 수급 가중치를 중립 처리했습니다."

    foreign = flow_signal.foreign_net_buy or 0.0
    institutional = flow_signal.institutional_net_buy or 0.0
    retail = flow_signal.retail_net_buy or 0.0
    denominator = abs(foreign) + abs(institutional) + abs(retail)
    if denominator <= 0:
        return 0.0, "수급 방향성이 혼조라서 중립 신호로 반영했습니다."

    score = _clip((foreign + institutional * 0.75 - retail * 0.35) / denominator, -1.0, 1.0)
    detail = (
        f"최근 집계 구간에서 외국인 {foreign:,.0f}{flow_signal.unit}, 기관 {institutional:,.0f}, "
        f"개인 {retail:,.0f} 흐름이 관측됐습니다."
    )
    return score, detail


def _analyst_score(analyst_context: dict | None, current_price: float) -> tuple[float | None, str]:
    if not analyst_context:
        return None, "애널리스트 컨텍스트가 없습니다."

    target_mean = analyst_context.get("target_mean")
    buy = float(analyst_context.get("buy", 0) or 0)
    hold = float(analyst_context.get("hold", 0) or 0)
    sell = float(analyst_context.get("sell", 0) or 0)

    score_parts: list[float] = []
    details: list[str] = []

    if target_mean and current_price:
        target_gap = (float(target_mean) / current_price - 1.0) * 100.0
        score_parts.append(_clip(target_gap / 18.0, -1.0, 1.0))
        details.append(f"평균 목표주가 괴리율 {target_gap:.2f}%.")

    consensus_total = buy + hold + sell
    if consensus_total > 0:
        consensus_score = (buy - sell) / consensus_total
        score_parts.append(_clip(consensus_score, -1.0, 1.0))
        details.append(f"매수 {buy:.0f} / 보유 {hold:.0f} / 매도 {sell:.0f}.")

    if not score_parts:
        return None, "목표주가 또는 투자의견 집계가 부족합니다."
    return float(np.mean(score_parts)), " ".join(details)


def _news_sentiment(news_items: list[dict] | None, ticker: str, name: str) -> tuple[float, str]:
    if not news_items:
        return 0.0, "관련 헤드라인이 부족해 뉴스 심리는 중립으로 처리했습니다."

    weighted_scores: list[float] = []
    weights: list[float] = []

    for item in news_items[:15]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        lower = title.lower()
        positive_hits = sum(weight for word, weight in POSITIVE_NEWS.items() if word in lower)
        negative_hits = sum(weight for word, weight in NEGATIVE_NEWS.items() if word in lower)
        raw_score = positive_hits - negative_hits
        raw_score = _clip(raw_score, -1.6, 1.6)

        if abs(raw_score) < 0.05:
            continue

        published = _parse_timestamp(item.get("published") or item.get("date"))
        recency_weight = 0.72
        if published is not None:
            age_hours = max((datetime.now(published.tzinfo) - published).total_seconds() / 3600.0, 0.0)
            if age_hours <= 24:
                recency_weight = 1.12
            elif age_hours <= 72:
                recency_weight = 1.0
            elif age_hours <= 168:
                recency_weight = 0.86

        source = str(item.get("source", "")).strip().lower()
        source_weight = 1.05 if source in TRUSTED_SOURCES else 1.0
        relevance = _headline_relevance(title, ticker, name)
        score = _clip(raw_score * source_weight * relevance, -1.4, 1.4)

        weighted_scores.append(score * recency_weight)
        weights.append(recency_weight)

    if not weighted_scores:
        return 0.0, "헤드라인 방향성이 약해 뉴스 심리를 중립으로 처리했습니다."

    sentiment = _clip(float(sum(weighted_scores) / max(sum(weights), 1e-9)), -1.0, 1.0)
    return sentiment, f"최근 헤드라인 {len(weighted_scores)}건 기준 뉴스 심리 점수 {sentiment:.2f}입니다."


def _build_driver(name: str, value: float, weight: float, detail: str) -> ForecastDriver:
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


def _return_cap(asset_type: str) -> float:
    return 3.6 if asset_type == "index" else 4.8


def _normalize_probabilities(*values: float) -> list[float]:
    cleaned = [max(float(value), 0.0) for value in values]
    total = sum(cleaned) or 1.0
    normalized = [round(value / total * 100.0, 1) for value in cleaned]
    drift = round(100.0 - sum(normalized), 1)
    if normalized:
        anchor = 1 if len(normalized) > 1 else 0
        normalized[anchor] = round(normalized[anchor] + drift, 1)
    return normalized


def _build_scenarios(
    *,
    current_price: float,
    expected_return_pct: float,
    daily_vol_pct: float,
    atr_pct: float,
    confidence: float,
    up_probability: float,
    disagreement_penalty: float,
    volatility_regime: float,
    asset_type: str,
    drivers: list[ForecastDriver],
) -> list[ForecastScenario]:
    cap = _return_cap(asset_type)
    scenario_span = max(daily_vol_pct * 0.82, atr_pct * 0.68, 0.45 if asset_type == "index" else 0.72)
    scenario_span *= 1.0 + disagreement_penalty * 0.22 + max(volatility_regime - 1.0, 0.0) * 0.28
    skew = _clip((up_probability - 50.0) / 50.0, -1.0, 1.0)
    bull_return = _clip(expected_return_pct + scenario_span * (0.72 + max(skew, 0.0) * 0.16), -cap, cap)
    bear_return = _clip(expected_return_pct - scenario_span * (0.72 + max(-skew, 0.0) * 0.16), -cap, cap)

    base_prob = _clip(
        40.0 + confidence * 0.12 - disagreement_penalty * 12.0 - max(volatility_regime - 1.0, 0.0) * 7.0,
        34.0,
        56.0,
    )
    tail_prob = max(100.0 - base_prob, 10.0)
    bull_prob = tail_prob * _clip(0.5 + skew * 0.32, 0.12, 0.88)
    bear_prob = max(tail_prob - bull_prob, 4.0)
    bull_prob, base_prob, bear_prob = _normalize_probabilities(bull_prob, base_prob, bear_prob)

    positive_driver = next((driver for driver in drivers if driver.contribution > 0), None)
    negative_driver = next((driver for driver in drivers if driver.contribution < 0), None)
    dominant_driver = drivers[0] if drivers else None

    return [
        ForecastScenario(
            name="Bull",
            price=round(current_price * (1.0 + bull_return / 100.0), 2),
            probability=bull_prob,
            description=(
                f"{positive_driver.name if positive_driver else '상방 신호'}가 유지되면 "
                f"{bull_return:+.2f}% 강세 경로가 열릴 수 있습니다."
            ),
        ),
        ForecastScenario(
            name="Base",
            price=round(current_price * (1.0 + expected_return_pct / 100.0), 2),
            probability=base_prob,
            description=(
                f"현재 신호 조합의 중심 경로입니다. "
                f"{dominant_driver.name if dominant_driver else '합성 신호'} 기준 {expected_return_pct:+.2f}%를 반영합니다."
            ),
        ),
        ForecastScenario(
            name="Bear",
            price=round(current_price * (1.0 + bear_return / 100.0), 2),
            probability=bear_prob,
            description=(
                f"{negative_driver.name if negative_driver else '변동성 압력'}이 커지면 "
                f"{bear_return:+.2f}% 약세 시나리오도 열어둬야 합니다."
            ),
        ),
    ]


def _build_risk_flags(
    *,
    volatility_regime: float,
    disagreement_penalty: float,
    news_score: float,
    volume_z: float,
    flow_signal: FlowSignal | None,
) -> list[str]:
    flags: list[str] = []
    if volatility_regime >= 1.25:
        flags.append("고변동성 구간이라 장중 밴드가 평소보다 넓게 형성될 수 있습니다.")
    if disagreement_penalty >= 0.45:
        flags.append("신호 간 충돌이 커서 한 방향으로 밀어붙이기엔 확신도가 낮습니다.")
    if abs(news_score) >= 0.55:
        flags.append("헤드라인 영향 비중이 높아 장중 뉴스 업데이트에 민감할 수 있습니다.")
    if volume_z <= -0.75:
        flags.append("거래량 확인이 약해 추세 지속 여부를 보수적으로 볼 필요가 있습니다.")
    if flow_signal and not flow_signal.available:
        flags.append("검증 가능한 수급 데이터가 없어 수급은 중립 가정으로 처리했습니다.")
    return flags[:4]


def _build_execution_bias(
    *,
    direction: str,
    up_probability: float,
    expected_return_pct: float,
    confidence: float,
    disagreement_penalty: float,
    volatility_regime: float,
) -> tuple[str, str]:
    if (
        direction == "up"
        and up_probability >= 64.0
        and confidence >= 72.0
        and disagreement_penalty < 0.34
        and volatility_regime < 1.25
    ):
        return "press_long", "신호 정렬이 좋아 추세 지속 대응이 우세합니다. 다만 시가 갭이 크면 추격보다 첫 눌림 확인이 좋습니다."
    if direction != "down" and up_probability >= 56.0 and expected_return_pct >= 0.35:
        return "lean_long", "상방 우위는 있지만 변동성을 감안해 분할 접근이나 눌림 매수 쪽이 더 안정적입니다."
    if direction == "down" and up_probability <= 36.0 and confidence >= 68.0:
        return "capital_preservation", "방어가 우선입니다. 신규 노출 확대보다 현금 비중과 손절 규율을 먼저 챙기는 편이 좋습니다."
    if direction == "down" or up_probability <= 44.0:
        return "reduce_risk", "하방 리스크 관리가 우선이며, 반등 신호가 재확인되기 전까지는 비중을 가볍게 보는 편이 좋습니다."
    return "stay_selective", "방향성 우위가 크지 않아 확인 신호를 더 기다리면서 선별적으로 대응하는 편이 좋습니다."


def _fallback_forecast(ticker: str, country_code: str, current_price: float, reference_date: str) -> NextDayForecast:
    target_date = next_trading_day(country_code, reference_date).isoformat()
    scenarios = [
        ForecastScenario(
            name="Bull",
            price=round(current_price * 1.01, 2) if current_price else 0.0,
            probability=25.0,
            description="가격 이력이 짧아 제한적인 상방 보정만 적용했습니다.",
        ),
        ForecastScenario(
            name="Base",
            price=round(current_price, 2),
            probability=50.0,
            description="보수적인 기준 시나리오입니다.",
        ),
        ForecastScenario(
            name="Bear",
            price=round(current_price * 0.99, 2) if current_price else 0.0,
            probability=25.0,
            description="가격 이력이 짧아 제한적인 하방 보정만 적용했습니다.",
        ),
    ]
    return NextDayForecast(
        target_date=target_date,
        reference_date=reference_date,
        reference_price=round(current_price, 2),
        direction="flat",
        up_probability=50.0,
        predicted_open=round(current_price, 2) if current_price else None,
        predicted_close=round(current_price, 2),
        predicted_high=round(current_price * 1.01, 2) if current_price else 0.0,
        predicted_low=round(current_price * 0.99, 2) if current_price else 0.0,
        predicted_return_pct=0.0,
        confidence=30.0,
        confidence_note=f"{ticker}는 학습에 필요한 가격 이력이 충분하지 않아 보수적인 중립 추정치를 사용했습니다.",
        news_sentiment=0.0,
        raw_signal=0.0,
        scenarios=scenarios,
        risk_flags=["가격 이력이 짧아 다음 거래일 예측을 보수적으로 해석해야 합니다."],
        execution_bias="stay_selective",
        execution_note="가격 이력이 짧아 방향 베팅보다 관찰과 추가 데이터 확보가 우선입니다.",
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
    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    current_price = float(close.iloc[-1])
    reference_date = str(df["date"].iloc[-1])
    target_date = next_trading_day(country_code, reference_date).isoformat()

    returns = np.log(close / close.shift(1)).dropna()
    daily_vol_pct = max(float(returns.tail(20).std() * 100), 0.35)
    long_vol_pct = max(float(returns.tail(min(60, len(returns))).std() * 100), daily_vol_pct)
    drift_pct = float(returns.tail(20).mean() * 100)

    ema_fast = EMAIndicator(close, window=min(10, len(close) - 1)).ema_indicator()
    ema_mid = EMAIndicator(close, window=min(21, len(close) - 1)).ema_indicator()
    ema_slow = EMAIndicator(close, window=min(55, len(close) - 1)).ema_indicator()
    rsi = RSIIndicator(close, window=min(14, len(close) - 1)).rsi()
    macd = MACD(
        close,
        window_fast=min(12, len(close) - 2),
        window_slow=min(26, len(close) - 1),
        window_sign=min(9, len(close) - 2),
    )
    atr = AverageTrueRange(high, low, close, window=min(14, len(close) - 1)).average_true_range()

    trend_5d = _pct_change(close, 5)
    trend_21d = _pct_change(close, 21)
    trend_55d = _pct_change(close, 55)
    last_body_pct = ((float(close.iloc[-1]) - float(open_.iloc[-1])) / max(float(open_.iloc[-1]), 0.01)) * 100.0
    ema_gap_pct = ((float(ema_fast.iloc[-1]) - float(ema_mid.iloc[-1])) / current_price * 100.0) if current_price else 0.0
    ema_stack_pct = ((float(ema_mid.iloc[-1]) - float(ema_slow.iloc[-1])) / current_price * 100.0) if current_price else 0.0
    stretch_to_fast_pct = ((current_price / max(float(ema_fast.iloc[-1]), 0.01)) - 1.0) * 100.0
    rsi_last = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else 50.0
    macd_hist_last = float(macd.macd_diff().iloc[-1]) if pd.notna(macd.macd_diff().iloc[-1]) else 0.0
    atr_pct = (float(atr.iloc[-1]) / current_price * 100.0) if current_price and pd.notna(atr.iloc[-1]) else daily_vol_pct

    day_range = max(float(high.iloc[-1]) - float(low.iloc[-1]), current_price * 0.001, 0.01)
    close_location = ((float(close.iloc[-1]) - float(low.iloc[-1])) / day_range) * 2.0 - 1.0

    volume_avg = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
    volume_std = float(volume.tail(20).std()) if len(volume) >= 20 else float(volume.std())
    volume_z = (float(volume.iloc[-1]) - volume_avg) / max(volume_std, volume_avg * 0.15, 1.0)

    volatility_regime = daily_vol_pct / max(long_vol_pct, 0.45)
    context_score = _clip(float(context_bias or 0.0), -1.0, 1.0)

    momentum_score = _clip((trend_5d * 0.65 + trend_21d * 0.35) / max(daily_vol_pct * 1.8, 0.8), -1.2, 1.2)
    trend_score = _clip((ema_gap_pct * 0.55 + ema_stack_pct * 0.45 + trend_55d * 0.25) / max(long_vol_pct * 1.9, 0.9), -1.15, 1.15)
    rsi_score = _clip(((50.0 - rsi_last) / 20.0) - (stretch_to_fast_pct / max(daily_vol_pct * 3.5, 1.6)), -1.0, 1.0)
    macd_score = _clip(macd_hist_last / max(current_price * 0.0018, 0.01), -1.0, 1.0)
    candle_score = _clip(close_location * 0.6 + _clip(last_body_pct / max(daily_vol_pct, 0.55), -1.0, 1.0) * 0.4, -1.0, 1.0)
    direction_sign = np.sign(last_body_pct if abs(last_body_pct) > 0.01 else trend_5d if abs(trend_5d) > 0.01 else trend_21d)
    volume_score = _clip((volume_z / 2.2) * (direction_sign or 1.0), -1.0, 1.0)
    regime_score = _clip((trend_21d * 0.5 + trend_55d * 0.35) / max(long_vol_pct * 2.0, 1.0) + context_score * 0.7 - max(volatility_regime - 1.15, 0.0) * 0.4, -1.2, 1.2)

    analyst_score, analyst_detail = _analyst_score(analyst_context, current_price)
    news_score, news_detail = _news_sentiment(news_items, ticker, name)
    flow_score, flow_detail = _flow_score(flow_signal)

    available_drivers = [
        ("추세 모멘텀", momentum_score, 0.17, f"5일 {trend_5d:.2f}%, 1개월 {trend_21d:.2f}% 흐름을 반영했습니다."),
        ("추세 정렬", trend_score, 0.15, f"EMA(10/21/55) 정렬과 장기 추세 괴리를 함께 평가했습니다."),
        ("과열/되돌림", rsi_score, 0.09, f"RSI(14) {rsi_last:.1f}, 단기 이격도 {stretch_to_fast_pct:.2f}% 수준입니다."),
        ("MACD 탄성", macd_score, 0.10, f"MACD 히스토그램 {macd_hist_last:.4f}로 추세 가속도를 확인했습니다."),
        ("캔들 주도권", candle_score, 0.08, f"당일 종가 위치 {close_location:.2f}, 캔들 몸통 {last_body_pct:.2f}%입니다."),
        ("거래량 확인", volume_score, 0.08, f"최근 거래량 z-score {volume_z:.2f}로 추세 확인 강도를 반영했습니다."),
        ("뉴스 심리", news_score, 0.12, news_detail),
        ("시장 체제", regime_score, 0.09, f"컨텍스트 바이어스 {context_score:.2f}, 변동성 체제 {volatility_regime:.2f}배입니다."),
    ]

    if analyst_score is not None:
        available_drivers.append(("애널리스트 컨센서스", analyst_score, 0.06, analyst_detail))
    if flow_score is not None:
        available_drivers.append(("수급 압력", flow_score, 0.06, flow_detail))

    total_weight = sum(weight for _, _, weight, _ in available_drivers) or 1.0
    drivers = [_build_driver(name_, value, weight / total_weight, detail) for name_, value, weight, detail in available_drivers]
    signal_strength = float(sum(driver.contribution for driver in drivers))
    disagreement = float(np.std([driver.value for driver in drivers])) if drivers else 0.0
    disagreement_penalty = _clip(disagreement / 0.9, 0.0, 0.7)
    volatility_penalty = _clip(max(volatility_regime - 1.0, 0.0), 0.0, 1.4)

    scale = 0.82 if asset_type == "index" else 1.0
    base_move = max(daily_vol_pct * 0.72, atr_pct * 0.58, 0.4 if asset_type == "index" else 0.58)
    expected_return_pct = drift_pct * 0.18 + signal_strength * base_move * 1.18 * scale + last_body_pct * 0.12
    expected_return_pct *= 1.0 - disagreement_penalty * 0.16
    expected_return_pct *= 1.0 - volatility_penalty * 0.10
    expected_return_pct = _clip(expected_return_pct, -_return_cap(asset_type), _return_cap(asset_type))

    up_probability = _clip(
        _sigmoid(signal_strength * 3.2 + regime_score * 0.9 + expected_return_pct / max(daily_vol_pct, 0.55) - disagreement_penalty * 0.8) * 100.0,
        6.0,
        94.0,
    )

    opening_return_pct = expected_return_pct * 0.38 + candle_score * base_move * 0.18
    predicted_open = current_price * (1.0 + opening_return_pct / 100.0)
    predicted_close = current_price * (1.0 + expected_return_pct / 100.0)
    intraday_range_pct = max(atr_pct * 0.85, daily_vol_pct * 0.82, 0.45 if asset_type == "index" else 0.68)
    intraday_range_pct *= 1.0 + max(volatility_regime - 1.0, 0.0) * 0.18
    band_factor = 0.52 + min(abs(expected_return_pct) / 4.0, 0.28) + disagreement_penalty * 0.08
    predicted_high = max(predicted_open, predicted_close) * (1.0 + intraday_range_pct * band_factor / 100.0)
    predicted_low = min(predicted_open, predicted_close) * (1.0 - intraday_range_pct * band_factor / 100.0)

    flat_threshold = 0.10 if asset_type == "index" else 0.12
    if abs(expected_return_pct) < flat_threshold:
        direction = "flat"
    else:
        direction = "up" if expected_return_pct > 0 else "down"

    coverage = len(drivers) / 10.0
    confidence = 47.0 + abs(signal_strength) * 28.0 + coverage * 10.0 - volatility_penalty * 8.0 - disagreement_penalty * 10.0
    confidence = _clip(confidence, 34.0, 93.0)
    scenarios = _build_scenarios(
        current_price=current_price,
        expected_return_pct=expected_return_pct,
        daily_vol_pct=daily_vol_pct,
        atr_pct=atr_pct,
        confidence=confidence,
        up_probability=up_probability,
        disagreement_penalty=disagreement_penalty,
        volatility_regime=volatility_regime,
        asset_type=asset_type,
        drivers=drivers,
    )
    risk_flags = _build_risk_flags(
        volatility_regime=volatility_regime,
        disagreement_penalty=disagreement_penalty,
        news_score=news_score,
        volume_z=volume_z,
        flow_signal=flow_signal,
    )
    execution_bias, execution_note = _build_execution_bias(
        direction=direction,
        up_probability=up_probability,
        expected_return_pct=expected_return_pct,
        confidence=confidence,
        disagreement_penalty=disagreement_penalty,
        volatility_regime=volatility_regime,
    )

    note_parts = [
        f"{ticker} {('지수' if asset_type == 'index' else '종목')}에 대해 추세, 과열도, 수급, 뉴스 심리를 합성한 다음 거래일 모델입니다.",
        f"최근 20일 실현 변동성 {daily_vol_pct:.2f}%, ATR {atr_pct:.2f}%를 반영했습니다.",
    ]
    if disagreement_penalty >= 0.45:
        note_parts.append("신호 간 의견이 갈려 기대 수익률과 신뢰도를 보수적으로 낮췄습니다.")
    if volatility_regime >= 1.25:
        note_parts.append("최근 변동성 체제가 높아 밴드 폭은 넓히고 확신도는 낮췄습니다.")
    if flow_signal and not flow_signal.available:
        note_parts.append("수급 데이터가 비어 있어 수급 가중치는 중립 처리했습니다.")

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
        scenarios=scenarios,
        risk_flags=risk_flags,
        execution_bias=execution_bias,
        execution_note=execution_note,
        flow_signal=flow_signal,
        drivers=ranked_drivers,
        model_version=MODEL_VERSION,
    )

