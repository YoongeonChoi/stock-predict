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
