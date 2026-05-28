"""Deterministic trade plan builder."""

from __future__ import annotations

import pandas as pd
from ta.volatility import AverageTrueRange
from math import exp
from typing import Any

from app.models.forecast import NextDayForecast
from app.models.market import MarketRegime, TradePlan, WeeklyTradePlan
from app.models.stock import BuySellGuide, PricePoint, TechnicalIndicators
from app.utils.market_calendar import trading_days_forward


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


def _finite_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not pd.notna(parsed):
        return default
    return parsed


def _rounded(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def _horizon_price(horizon: Any, field: str, reference_price: float, log_field: str) -> float | None:
    direct = _finite_float(getattr(horizon, field, None))
    if direct is not None and direct > 0:
        return direct
    log_return = _finite_float(getattr(horizon, log_field, None))
    if log_return is None or reference_price <= 0:
        return None
    return reference_price * exp(log_return)


def _weekly_target_date(horizon: Any, reference_date: str | None) -> str:
    target_date = str(getattr(horizon, "target_date", "") or "").strip()
    if target_date:
        return target_date
    if not reference_date:
        return ""
    try:
        dates = trading_days_forward("KR", reference_date, 5)
        return dates[-1].isoformat() if len(dates) >= 5 else reference_date
    except Exception:
        return reference_date


def _weekly_signal(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value >= 0.04:
        return "bullish"
    if value <= -0.04:
        return "bearish"
    return "neutral"


def _event_uncertainty(event_context: Any | None) -> float:
    if event_context is None:
        return 0.0
    if isinstance(event_context, dict):
        return _clip(_finite_float(event_context.get("uncertainty"), 0.0) or 0.0, 0.0, 1.0)
    return _clip(_finite_float(getattr(event_context, "uncertainty", None), 0.0) or 0.0, 0.0, 1.0)


def _flow_detail(flow_signal: Any | None) -> tuple[str, str]:
    if flow_signal is None:
        return "neutral", "수급 데이터는 이번 판단에서 보조 신호로 제한적으로 반영했습니다."
    available = bool(getattr(flow_signal, "available", False))
    if not available:
        status = str(getattr(flow_signal, "data_status", "") or "").strip()
        if status == "eod_pending":
            return "neutral", "수급 데이터는 장 마감 집계 전이라 대기 상태입니다."
        return "neutral", "수급 데이터가 제한적이라 가격·변동성 신호를 우선했습니다."
    foreign_5d = _finite_float(getattr(flow_signal, "foreign_net_buy_5d", None), 0.0) or 0.0
    institutional_5d = _finite_float(getattr(flow_signal, "institutional_net_buy_5d", None), 0.0) or 0.0
    combined = foreign_5d + institutional_5d
    if combined > 0:
        return "bullish", "최근 5거래일 외국인·기관 합산 수급이 순매수 쪽입니다."
    if combined < 0:
        return "bearish", "최근 5거래일 외국인·기관 합산 수급이 순매도 쪽입니다."
    return "neutral", "최근 5거래일 수급은 한쪽으로 크게 기울지 않았습니다."


def _research_signal(research_context: list[Any] | None) -> tuple[str, str, int]:
    if not research_context:
        return "neutral", "공식 리서치 메타데이터는 아직 종목 판단에 직접 매칭되지 않았습니다.", 0

    signal_score = 0
    titles: list[str] = []
    for item in research_context[:3]:
        signal = str(item.get("signal") if isinstance(item, dict) else getattr(item, "signal", "") or "")
        if signal == "bullish":
            signal_score += 1
        elif signal == "bearish":
            signal_score -= 1
        title = str(item.get("title") if isinstance(item, dict) else getattr(item, "title", "") or "").strip()
        if title:
            titles.append(title)

    tone = "bullish" if signal_score >= 2 else "bearish" if signal_score <= -2 else "neutral"
    lead = " / ".join(titles[:2])
    detail = (
        f"공식·허용 리서치 메타데이터 {len(research_context)}건을 확인했습니다."
        if not lead
        else f"공식·허용 리서치 메타데이터 {len(research_context)}건을 확인했습니다: {lead[:180]}"
    )
    return tone, detail, len(research_context)


def build_weekly_trade_plan(
    *,
    ticker: str,
    current_price: float,
    price_history: list[PricePoint],
    technical: TechnicalIndicators,
    buy_sell_guide: BuySellGuide,
    weekly_horizon: Any | None,
    market_regime: MarketRegime | None = None,
    event_context: Any | None = None,
    flow_signal: Any | None = None,
    distribution_evidence: list[Any] | None = None,
    research_context: list[Any] | None = None,
    source_freshness: list[dict | Any] | None = None,
    reference_date: str | None = None,
    partial: bool = False,
    fallback_reason: str | None = None,
) -> WeeklyTradePlan:
    if current_price <= 0:
        return WeeklyTradePlan(
            horizon_days=5,
            target_date=reference_date or "",
            reference_date=reference_date or "",
            reference_price=0.0,
            action="avoid",
            partial=True,
            fallback_reason=fallback_reason or "weekly_trade_plan_price_missing",
            data_quality="현재가가 없어 5거래일 매수·매도 가격을 계산하지 않았습니다.",
            evidence=[
                {
                    "key": "price",
                    "label": "가격 데이터",
                    "signal": "bearish",
                    "detail": "현재가와 OHLC 시계열이 확보되면 다시 계산합니다.",
                }
            ],
            source_freshness=source_freshness or [],
        )

    reference_date = reference_date or (price_history[-1].date if price_history else "")
    atr_pct = _atr_pct(price_history, current_price)
    event_uncertainty = _event_uncertainty(event_context)
    ma20 = _last_value(technical.ma_20)
    ma60 = _last_value(technical.ma_60)
    trend_supported = bool(ma20 is None or current_price >= ma20 * 0.985)
    if ma60 is not None:
        trend_supported = trend_supported and current_price >= ma60 * 0.97

    if weekly_horizon is None:
        risk_buffer_pct = _clip(max(atr_pct * 1.15, 3.0), 2.8, 9.0)
        buy_high = min(buy_sell_guide.buy_zone_high, current_price * 0.995)
        buy_low = max(buy_sell_guide.buy_zone_low, buy_high * (1.0 - min(atr_pct, 4.5) / 100.0))
        if buy_low > buy_high:
            buy_low = buy_high * 0.985
        sell_low = max(buy_sell_guide.sell_zone_low, current_price * 1.015)
        sell_high = max(sell_low, min(buy_sell_guide.sell_zone_high, current_price * 1.055))
        buy_price = (buy_low + buy_high) / 2.0
        stop_loss = min(buy_price * (1.0 - risk_buffer_pct / 100.0), current_price * 0.965)
        risk_reward = ((sell_low - buy_price) / (buy_price - stop_loss)) if buy_price > stop_loss else 0.0
        return WeeklyTradePlan(
            horizon_days=5,
            target_date=_weekly_target_date(weekly_horizon, reference_date),
            reference_date=reference_date,
            reference_price=round(current_price, 2),
            action="wait_pullback",
            buy_price=round(buy_price, 2),
            buy_zone_low=round(buy_low, 2),
            buy_zone_high=round(buy_high, 2),
            sell_price=round(sell_low, 2),
            sell_zone_low=round(sell_low, 2),
            sell_zone_high=round(sell_high, 2),
            stop_loss=round(stop_loss, 2),
            expected_return_pct=None,
            expected_excess_return_pct=None,
            p_up=None,
            p_flat=None,
            p_down=None,
            confidence=32.0,
            risk_reward_estimate=round(max(risk_reward, 0.0), 2),
            evidence=[
                {
                    "key": "distribution",
                    "label": "5거래일 분포",
                    "signal": "neutral",
                    "detail": "정밀 분포 계산이 아직 없어 기존 가격 밴드와 ATR로 대기 구간만 표시합니다.",
                }
            ],
            source_freshness=source_freshness or [],
            partial=True,
            fallback_reason=fallback_reason or "weekly_trade_plan_distribution_pending",
            data_quality="5거래일 분포가 준비되지 않아 가격·ATR 기반 대기 구간으로 먼저 표시합니다.",
        )

    q10 = _horizon_price(weekly_horizon, "price_q10", current_price, "q10") or current_price * 0.96
    q25 = _horizon_price(weekly_horizon, "price_q25", current_price, "q25") or current_price * 0.985
    q50 = _horizon_price(weekly_horizon, "price_q50", current_price, "q50") or current_price
    q75 = _horizon_price(weekly_horizon, "price_q75", current_price, "q75") or current_price * 1.02
    q90 = _horizon_price(weekly_horizon, "price_q90", current_price, "q90") or current_price * 1.04

    distribution_buy_low = min(q25, q50)
    distribution_buy_high = max(q25, q50)
    chase_limit = current_price * (1.0 + min(max(atr_pct * 0.22, 0.4), 1.3) / 100.0)
    guide_ceiling = buy_sell_guide.buy_zone_high * 1.01 if buy_sell_guide.buy_zone_high else chase_limit
    buy_high = min(distribution_buy_high, chase_limit, guide_ceiling)
    buy_low = max(
        min(distribution_buy_low, buy_high),
        buy_sell_guide.buy_zone_low * 0.985 if buy_sell_guide.buy_zone_low else current_price * 0.95,
        current_price * (1.0 - min(max(atr_pct * 1.05, 1.6), 7.5) / 100.0),
    )
    if buy_low > buy_high:
        buy_high = min(chase_limit, guide_ceiling, max(distribution_buy_high, current_price * 0.998))
        buy_low = min(buy_high, current_price) * (1.0 - min(max(atr_pct * 0.45, 0.8), 3.2) / 100.0)
    buy_price = (buy_low + buy_high) / 2.0

    distribution_sell_low = max(min(q75, q90), buy_price * 1.006)
    distribution_sell_high = max(q75, q90, distribution_sell_low)
    guide_sell_low = buy_sell_guide.sell_zone_low or current_price * 1.025
    guide_sell_high = buy_sell_guide.sell_zone_high or current_price * 1.06
    sell_low = max(distribution_sell_low, guide_sell_low * 0.97, buy_price * 1.012)
    sell_high = min(distribution_sell_high, guide_sell_high * 1.015, current_price * (1.0 + max(atr_pct * 2.2, 3.0) / 100.0))
    if sell_high < sell_low:
        sell_low = max(buy_price * 1.01, min(distribution_sell_low, guide_sell_low))
        sell_high = max(sell_low, min(max(distribution_sell_high, sell_low * 1.015), guide_sell_high * 1.015))
    sell_price = (sell_low + sell_high) / 2.0

    atr_stop = buy_price * (1.0 - _clip(max(atr_pct * 1.15, 3.0), 2.8, 9.0) / 100.0)
    stop_loss = max(min(atr_stop, q10), buy_price * 0.9)
    if stop_loss >= buy_price:
        stop_loss = buy_price * 0.965

    expected_return_pct = (_finite_float(getattr(weekly_horizon, "mean_return_raw", None), 0.0) or 0.0) * 100.0
    expected_excess_return_pct = (_finite_float(getattr(weekly_horizon, "mean_return_excess", None), 0.0) or 0.0) * 100.0
    p_up = _finite_float(getattr(weekly_horizon, "p_up", None), 0.0) or 0.0
    p_flat = _finite_float(getattr(weekly_horizon, "p_flat", None), 0.0) or 0.0
    p_down = _finite_float(getattr(weekly_horizon, "p_down", None), 0.0) or 0.0
    confidence = _finite_float(getattr(weekly_horizon, "confidence", None), 0.0) or 0.0
    research_tone, research_detail, research_count = _research_signal(research_context)

    risk_reward = ((sell_price - buy_price) / (buy_price - stop_loss)) if buy_price > stop_loss else 0.0
    risk_off = getattr(market_regime, "stance", None) == "risk_off"
    risk_on = getattr(market_regime, "stance", None) == "risk_on"

    action: str = "wait_pullback"
    if p_up < 39.0 or (expected_return_pct < -0.9 and confidence >= 48.0):
        action = "avoid"
    elif p_up < 46.0 or (risk_off and (p_up < 53.0 or confidence < 58.0)) or event_uncertainty >= 0.72:
        action = "reduce_risk"
    elif p_up >= 62.0 and confidence >= 60.0 and risk_reward >= 1.25 and not risk_off and trend_supported:
        action = "accumulate" if current_price <= buy_high * 1.004 else "breakout_watch"
    elif p_up >= 55.0 and confidence >= 50.0 and risk_reward >= 1.05 and (risk_on or trend_supported):
        action = "breakout_watch" if current_price > buy_high else "wait_pullback"

    if research_tone == "bearish" and action in {"accumulate", "breakout_watch"}:
        action = "wait_pullback"
    elif research_tone == "bearish" and action == "wait_pullback" and p_up < 55.0:
        action = "reduce_risk"

    if action in {"avoid", "reduce_risk"}:
        buy_price_for_rr = current_price
        sell_price = max(current_price * 1.006, min(sell_price, buy_sell_guide.sell_zone_low or sell_price))
        stop_loss = min(current_price * (1.0 - max(atr_pct * 0.75, 2.0) / 100.0), q10)
        risk_reward = ((sell_price - buy_price_for_rr) / (buy_price_for_rr - stop_loss)) if buy_price_for_rr > stop_loss else 0.0

    evidence: list[dict[str, str]] = [
        {
            "key": "distribution",
            "label": "5거래일 분포",
            "signal": "bullish" if p_up >= 58.0 else "bearish" if p_up <= 44.0 else "neutral",
            "detail": f"상승 {p_up:.1f}%, 보합 {p_flat:.1f}%, 하락 {p_down:.1f}%로 계산했습니다.",
        },
        {
            "key": "price_band",
            "label": "가격·ATR",
            "signal": "bullish" if trend_supported else "neutral",
            "detail": f"ATR {atr_pct:.1f}%와 현재가를 사용해 추격 매수 상단을 제한했습니다.",
        },
    ]
    if market_regime:
        evidence.append(
            {
                "key": "market_regime",
                "label": "시장 국면",
                "signal": "bullish" if market_regime.stance == "risk_on" else "bearish" if market_regime.stance == "risk_off" else "neutral",
                "detail": market_regime.summary or f"시장 국면은 {market_regime.stance}입니다.",
            }
        )
    flow_signal_label, flow_signal_detail = _flow_detail(flow_signal)
    evidence.append(
        {
            "key": "flow",
            "label": "수급",
            "signal": flow_signal_label,
            "detail": flow_signal_detail,
        }
    )
    if event_context:
        summary = getattr(event_context, "summary", "") if not isinstance(event_context, dict) else str(event_context.get("summary") or "")
        evidence.append(
            {
                "key": "event",
                "label": "뉴스·공시 이벤트",
                "signal": "bearish" if event_uncertainty >= 0.6 else "neutral",
                "detail": summary or "뉴스·공시 이벤트는 숫자 생성이 아니라 리스크 보정 신호로만 반영했습니다.",
            }
        )
    if research_count > 0:
        evidence.append(
            {
                "key": "official_research",
                "label": "공식 리서치",
                "signal": research_tone,
                "detail": research_detail,
            }
        )
    for item in distribution_evidence or []:
        contribution = _finite_float(getattr(item, "contribution", None), None)
        detail = str(getattr(item, "detail", "") or "")
        evidence.append(
            {
                "key": str(getattr(item, "key", "distribution_evidence")),
                "label": str(getattr(item, "label", "분포 근거")),
                "signal": _weekly_signal(contribution),
                "detail": detail[:220],
            }
        )
        if len(evidence) >= 7:
            break

    data_quality = "5거래일 분포, 가격·변동성, 시장 국면, 이벤트 보조 신호를 함께 반영했습니다."
    if research_count > 0:
        data_quality = f"{data_quality} 공식 리서치 메타데이터 {research_count}건도 근거 상태에 포함했습니다."
    if partial:
        data_quality = "정밀 소스 일부가 제한돼 확보된 5거래일 분포와 가격·변동성 신호를 우선 반영했습니다."
    if event_uncertainty >= 0.72:
        data_quality = f"{data_quality} 이벤트 불확실성이 높아 실행 강도를 낮췄습니다."

    return WeeklyTradePlan(
        horizon_days=5,
        target_date=_weekly_target_date(weekly_horizon, reference_date),
        reference_date=reference_date,
        reference_price=round(current_price, 2),
        action=action,  # type: ignore[arg-type]
        buy_price=_rounded(buy_price),
        buy_zone_low=_rounded(buy_low),
        buy_zone_high=_rounded(buy_high),
        sell_price=_rounded(sell_price),
        sell_zone_low=_rounded(sell_low),
        sell_zone_high=_rounded(sell_high),
        stop_loss=_rounded(stop_loss),
        expected_return_pct=round(expected_return_pct, 2),
        expected_excess_return_pct=round(expected_excess_return_pct, 2),
        p_up=round(p_up, 1),
        p_flat=round(p_flat, 1),
        p_down=round(p_down, 1),
        confidence=round(confidence, 1),
        risk_reward_estimate=round(max(risk_reward, 0.0), 2),
        evidence=evidence,
        source_freshness=source_freshness or [],
        partial=partial,
        fallback_reason=fallback_reason,
        data_quality=data_quality,
    )


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
            setup_label=f"{ticker} 관찰 전용",
            action="avoid",
            conviction=30.0,
            thesis=["가격 데이터가 부족해 실행 플랜을 잠시 보류했습니다."],
            invalidation="데이터를 다시 불러온 뒤 판단을 이어가세요.",
        )

    ma20 = _last_value(technical.ma_20)
    ma60 = _last_value(technical.ma_60)
    rsi = _last_value(technical.rsi_14) or 50.0
    macd_hist = _last_value(technical.macd_hist) or 0.0
    atr_pct = _atr_pct(price_history, current_price)

    regime_tailwind = 0.0
    if market_regime:
        regime_tailwind = 0.18 if market_regime.stance == "risk_on" else -0.18 if market_regime.stance == "risk_off" else 0.0

    up_probability = float(next_day_forecast.up_probability) if next_day_forecast else 50.0
    forecast_direction = str(next_day_forecast.direction) if next_day_forecast else "flat"
    forecast_return_pct = float(next_day_forecast.predicted_return_pct) if next_day_forecast else 0.0
    risk_off_tape = bool(market_regime and market_regime.stance == "risk_off")
    bullish_forecast = bool(next_day_forecast and up_probability >= 58 and forecast_direction != "down")
    bearish_forecast = bool(next_day_forecast and (up_probability <= 42 or forecast_direction == "down"))
    near_buy_zone = current_price <= buy_sell_guide.buy_zone_high * 1.02
    premium_to_fair = current_price >= buy_sell_guide.fair_value * 1.05
    trend_confirmed = bool(ma20 and current_price > ma20 and (ma60 is None or current_price >= ma60))
    risk_buffer_pct = max(atr_pct * 1.25, 4.0)

    projected_entry_low = max(buy_sell_guide.buy_zone_low, current_price * 0.985)
    projected_entry_high = min(buy_sell_guide.buy_zone_high, current_price * 1.01)
    projected_entry_reference = (
        (projected_entry_low + projected_entry_high) / 2.0
        if projected_entry_low <= projected_entry_high
        else current_price
    )
    projected_stop = projected_entry_reference * (1.0 - risk_buffer_pct / 100.0)
    projected_take_profit = max(
        buy_sell_guide.fair_value,
        current_price * (1.0 + max(forecast_return_pct, 1.8) / 100.0),
    )
    projected_risk_reward = 0.0
    if projected_entry_reference > projected_stop:
        projected_risk_reward = max(
            (projected_take_profit - projected_entry_reference) / (projected_entry_reference - projected_stop),
            0.0,
        )
    long_ready = (not risk_off_tape) and (not premium_to_fair) and (trend_confirmed or projected_risk_reward >= 1.25)
    should_reduce_risk = bool(
        bearish_forecast
        or up_probability <= 45.0
        or forecast_direction == "down"
        or (risk_off_tape and premium_to_fair)
        or ((not trend_confirmed or macd_hist < 0) and projected_risk_reward < 1.1)
    )

    if should_reduce_risk:
        setup_label = "리스크 축소"
        action = "reduce_risk"
        entry_low = None
        entry_high = None
        hold_days = 3
    elif bullish_forecast and near_buy_zone and long_ready:
        setup_label = "눌림목 분할 대응"
        action = "accumulate"
        entry_low = max(buy_sell_guide.buy_zone_low, current_price * 0.985)
        entry_high = min(buy_sell_guide.buy_zone_high, current_price * 1.01)
        hold_days = 8
    elif bullish_forecast and trend_confirmed and macd_hist >= 0 and long_ready:
        setup_label = "추세 지속 확인"
        action = "breakout_watch"
        entry_low = current_price * 0.995
        entry_high = current_price * 1.02
        hold_days = 5
    elif rsi < 38 and next_day_forecast and up_probability >= 55 and long_ready:
        setup_label = "되돌림 스윙"
        action = "accumulate"
        entry_low = max(buy_sell_guide.buy_zone_low, current_price * 0.98)
        entry_high = min(current_price * 1.005, buy_sell_guide.buy_zone_high * 1.02)
        hold_days = 6
    else:
        setup_label = "확인 대기"
        action = "wait_pullback"
        entry_low = buy_sell_guide.buy_zone_low
        entry_high = min(buy_sell_guide.buy_zone_high, current_price * 0.99)
        hold_days = 5

    stop_loss = None
    take_profit_1 = None
    take_profit_2 = None
    if entry_low is not None:
        stop_loss = entry_low * (1.0 - risk_buffer_pct / 100.0)
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
        if next_day_forecast.direction == "down":
            thesis.append(
                f"단기 확률모형은 {next_day_forecast.target_date}까지 하방 압력이 남아 있다고 보고, 상승 확률은 {next_day_forecast.up_probability:.1f}% 수준에 머뭅니다."
            )
        elif next_day_forecast.direction == "up":
            thesis.append(
                f"단기 확률모형은 {next_day_forecast.target_date}까지 상방 시도를 열어 두지만, 상승 확률 우위는 {next_day_forecast.up_probability:.1f}% 수준입니다."
            )
        else:
            thesis.append(
                f"단기 확률모형은 {next_day_forecast.target_date}까지 뚜렷한 한 방향보다 혼조 흐름을 가정하며, 상승 확률은 {next_day_forecast.up_probability:.1f}%입니다."
            )
    if buy_sell_guide.fair_value:
        thesis.append(
            f"현재 가격은 적정가 대비 {((current_price / buy_sell_guide.fair_value) - 1.0) * 100:+.1f}% 위치에 있어 추격 여부를 더 신중히 봐야 합니다."
        )
    else:
        thesis.append("적정가 추정이 넓지 않아 비중과 타이밍을 더 보수적으로 잡는 편이 낫습니다.")
    if market_regime:
        if market_regime.stance == "risk_on":
            thesis.append("시장 국면이 완전한 역풍은 아니어서 추세 확인이 붙으면 해석 여지는 남아 있습니다.")
        elif market_regime.stance == "risk_off":
            thesis.append("시장 국면이 방어적으로 기울어 있어 공격적 확대에는 불리합니다.")
        else:
            thesis.append("시장 국면이 한쪽으로 크게 기울지 않아 선별 대응이 더 중요합니다.")
    else:
        thesis.append("시장 국면 보조 신호가 제한적이라 실행 플랜도 유연하게 가져가는 편이 좋습니다.")

    invalidation = "제안한 손절 구간 아래로 일봉 마감이 이어지면 현재 가설은 무효로 봅니다."
    if action == "reduce_risk":
        invalidation = "20일선 구조를 다시 회복하고 단기 확률이 개선되면 방어 대응을 재평가합니다."
    elif action == "wait_pullback":
        invalidation = "진입 밴드 재확인 없이 가격만 먼저 달아나면 추격하지 않고 다음 눌림을 기다립니다."

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


def build_short_horizon_trade_plan(
    *,
    ticker: str,
    current_price: float,
    price_history: list[PricePoint],
    technical: TechnicalIndicators,
    buy_sell_guide: BuySellGuide,
    next_day_forecast: NextDayForecast | None,
    market_regime: MarketRegime | None = None,
) -> TradePlan:
    if current_price <= 0 or next_day_forecast is None:
        return TradePlan(
            setup_label=f"{ticker} 단기 관찰",
            action="avoid",
            conviction=26.0,
            expected_holding_days=1,
            thesis=["다음 거래일 전용 플랜을 만들 데이터가 부족해 관찰 우선으로 둡니다."],
            invalidation="다음 거래일 예측과 가격 데이터가 함께 확보되면 다시 계산합니다.",
        )

    ma20 = _last_value(technical.ma_20)
    atr_pct = _atr_pct(price_history, current_price)
    up_probability = float(next_day_forecast.up_probability or 0.0)
    confidence = float(next_day_forecast.confidence or 0.0)
    predicted_return_pct = float(next_day_forecast.predicted_return_pct or 0.0)
    predicted_open = float(next_day_forecast.predicted_open or current_price or 0.0)
    predicted_close = float(next_day_forecast.predicted_close or current_price or 0.0)
    predicted_high = float(next_day_forecast.predicted_high or current_price or 0.0)
    predicted_low = float(next_day_forecast.predicted_low or current_price or 0.0)
    regime_stance = getattr(market_regime, "stance", "neutral")
    trend_supported = ma20 is None or current_price >= ma20 * 0.992
    risk_off_tape = regime_stance == "risk_off"

    base_entry = predicted_open if predicted_open > 0 else current_price
    buy_low = float(getattr(buy_sell_guide, "buy_zone_low", 0.0) or current_price)
    buy_high = float(getattr(buy_sell_guide, "buy_zone_high", 0.0) or current_price)
    entry_low = max(min(base_entry, current_price) * 0.997, buy_low * 0.995)
    entry_high = min(max(base_entry, current_price) * 1.003, max(buy_high * 1.005, current_price * 1.008))
    if entry_low > entry_high:
        midpoint = max(base_entry, current_price)
        entry_low = midpoint * 0.997
        entry_high = midpoint * 1.003

    entry_reference = (entry_low + entry_high) / 2.0
    intraday_risk_pct = max(((entry_reference - predicted_low) / entry_reference) * 100.0, 0.0) if entry_reference > 0 else 0.0
    stop_buffer_pct = _clip(max(intraday_risk_pct * 0.9, atr_pct * 0.45, 1.4), 1.4, 4.8)
    stop_loss = max(entry_reference * (1.0 - stop_buffer_pct / 100.0), predicted_low * 0.998 if predicted_low > 0 else 0.0)
    take_profit_1 = max(predicted_close, entry_reference * 1.006)
    take_profit_2 = max(predicted_high, take_profit_1 * 1.01)

    action = "wait_pullback"
    setup_label = "장중 확인 대기"
    if predicted_return_pct <= 0 or up_probability < 52.0 or next_day_forecast.direction == "down":
        action = "reduce_risk" if (risk_off_tape or predicted_return_pct < 0) else "wait_pullback"
        setup_label = "리스크 축소" if action == "reduce_risk" else "짧은 반등 확인"
    elif up_probability >= 61.0 and confidence >= 64.0 and trend_supported and not risk_off_tape:
        action = "accumulate"
        setup_label = "다음 거래일 집중 매수"
    elif up_probability >= 56.0 and predicted_return_pct >= 0.25:
        action = "breakout_watch"
        setup_label = "장초반 돌파 확인"

    if action == "reduce_risk":
        entry_low = None
        entry_high = None
        stop_loss = current_price * (1.0 - _clip(max(atr_pct * 0.35, 1.2), 1.2, 3.0) / 100.0)
        take_profit_1 = max(predicted_close, current_price * 1.003)
        take_profit_2 = max(predicted_high, take_profit_1 * 1.006)
        entry_reference = current_price

    risk_reward = 0.0
    if stop_loss and take_profit_1 and entry_reference > stop_loss:
        risk_reward = max((take_profit_1 - entry_reference) / (entry_reference - stop_loss), 0.0)

    regime_note = (
        "시장 국면이 risk-on이라 단기 추세 추종에 상대적으로 유리합니다."
        if regime_stance == "risk_on"
        else "시장 국면이 risk-off라 장중 반등도 짧게 보는 편이 낫습니다."
        if regime_stance == "risk_off"
        else "시장 국면이 혼조라 진입 가격과 손절을 더 엄격하게 봐야 합니다."
    )
    thesis = [
        f"{next_day_forecast.target_date} 기준 상승 확률 {up_probability:.1f}%, 예상 수익률 {predicted_return_pct:+.2f}%입니다.",
        f"예상 고가 {predicted_high:.2f}, 예상 저가 {predicted_low:.2f} 범위 안에서 짧게 대응하는 구조입니다.",
        regime_note,
    ]
    if next_day_forecast.execution_note:
        thesis.append(next_day_forecast.execution_note)

    conviction = 20.0 + up_probability * 0.35 + confidence * 0.35 + min(risk_reward, 3.2) * 8.0
    if regime_stance == "risk_on":
        conviction += 5.0
    elif regime_stance == "risk_off":
        conviction -= 6.0
    conviction = round(_clip(conviction, 24.0, 92.0), 1)

    invalidation = "다음 거래일 장중 손절가를 이탈하면 같은 날 재진입보다 시나리오 종료를 우선합니다."
    if action == "reduce_risk":
        invalidation = "다음 거래일 상방 확률과 종가 구조가 함께 회복되기 전까지 방어 대응을 유지합니다."

    return TradePlan(
        setup_label=setup_label,
        action=action,
        conviction=conviction,
        entry_low=round(entry_low, 2) if entry_low is not None else None,
        entry_high=round(entry_high, 2) if entry_high is not None else None,
        stop_loss=round(stop_loss, 2) if stop_loss is not None else None,
        take_profit_1=round(take_profit_1, 2) if take_profit_1 is not None else None,
        take_profit_2=round(take_profit_2, 2) if take_profit_2 is not None else None,
        expected_holding_days=1,
        risk_reward_estimate=round(risk_reward, 2),
        thesis=thesis[:4],
        invalidation=invalidation,
    )
