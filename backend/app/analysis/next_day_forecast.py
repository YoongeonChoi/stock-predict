"""Distribution-first next-trading-day forecast wrapper."""

from __future__ import annotations

from datetime import datetime
from math import exp

from app.analysis.distributional_return_engine import MODEL_VERSION, build_distributional_forecast
from app.models.forecast import FlowSignal, ForecastDriver, ForecastScenario, NextDayForecast
from app.utils.market_calendar import next_trading_day


def _driver_signal(value: float) -> str:
    if value > 0.05:
        return "bullish"
    if value < -0.05:
        return "bearish"
    return "neutral"


def _price_from_return(reference_price: float, log_return: float) -> float:
    if reference_price <= 0:
        return 0.0
    return round(reference_price * exp(log_return), 2)


def _build_execution_bias(
    *,
    direction: str,
    up_probability: float,
    confidence: float,
    predicted_return_pct: float,
    regime: str,
) -> tuple[str, str]:
    if direction == "up" and up_probability >= 63.0 and confidence >= 72.0 and regime == "risk_on":
        return "press_long", "상승 확률과 체제 정렬이 모두 좋아 추세 지속 대응이 가장 타당합니다."
    if direction == "up" and up_probability >= 56.0 and predicted_return_pct >= 0.3:
        return "lean_long", "상방 우위는 분명하지만 변동성 구간이라 눌림 확인 후 접근이 더 안정적입니다."
    if direction == "down" and up_probability <= 37.0 and confidence >= 66.0:
        return "capital_preservation", "하방 확률과 체제 위험이 함께 높아 방어와 현금 관리가 우선입니다."
    if direction == "down" or regime == "risk_off":
        return "reduce_risk", "체제와 분포가 모두 보수적으로 기울어 비중 축소가 우선입니다."
    return "stay_selective", "확률 우위가 크지 않아 확인 신호를 더 보면서 선별적으로 대응하는 편이 좋습니다."


def _build_risk_flags(
    *,
    regime: str,
    q10: float,
    q90: float,
    event_uncertainty: float,
    confidence: float,
) -> list[str]:
    flags: list[str] = []
    if regime == "risk_off":
        flags.append("시장 체제가 risk-off 쪽으로 기울어 있어 단기 반등 시도도 변동성이 크게 나올 수 있습니다.")
    if (q90 - q10) * 100.0 >= 4.0:
        flags.append("예측 구간 폭이 넓어 분포 tail 리스크를 함께 봐야 합니다.")
    if event_uncertainty >= 0.55:
        flags.append("최근 이벤트 불확실성이 높아 뉴스·공시 해석을 보수적으로 볼 필요가 있습니다.")
    if confidence <= 46.0:
        flags.append("가용 데이터가 제한적이어서 분포 밴드를 기준으로 보수적으로 해석하는 편이 좋습니다.")
    return flags[:3]


def _map_drivers(evidence) -> list[ForecastDriver]:
    drivers = [
        ForecastDriver(
            name=item.label,
            value=round(item.value, 4),
            signal=_driver_signal(item.contribution),
            weight=round(item.weight, 4),
            contribution=round(item.contribution, 4),
            detail=item.detail,
        )
        for item in evidence
    ]
    drivers.sort(key=lambda item: abs(item.contribution), reverse=True)
    return drivers[:6]


def _fallback_forecast(ticker: str, country_code: str, current_price: float, reference_date: str) -> NextDayForecast:
    target_date = next_trading_day(country_code, reference_date).isoformat()
    scenarios = [
        ForecastScenario(
            name="Bull",
            price=round(current_price * 1.01, 2) if current_price else 0.0,
            probability=25.0,
            description="가격 이력이 짧아 제한적인 상방 밴드만 계산했습니다.",
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
            description="가격 이력이 짧아 제한적인 하방 밴드만 계산했습니다.",
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
        raw_confidence=30.0,
        calibrated_probability=0.3,
        probability_edge=0.0,
        confidence_calibrator="fallback_constant",
        calibration_snapshot={
            "prediction_type": "next_day",
            "horizon_bucket": 1,
            "raw_support": 0.3,
            "raw_confidence": 30.0,
            "distribution_support": 0.3,
            "analog_support": None,
            "analog_available": False,
            "regime_support": 0.0,
            "edge_support": 0.0,
            "agreement_support": None,
            "agreement_available": False,
            "data_quality_support": 0.15,
            "uncertainty_support": 0.7,
            "volatility_support": 0.4,
            "volatility_ratio": 1.0,
        },
        confidence_note=f"{ticker}는 분포 예측에 필요한 가격 이력이 충분하지 않아 보수적인 중립 추정치를 사용했습니다.",
        news_sentiment=0.0,
        raw_signal=0.0,
        scenarios=scenarios,
        risk_flags=["가격 이력이 짧아 다음 거래일 예측을 보수적으로 해석해야 합니다."],
        execution_bias="stay_selective",
        execution_note="추가 가격 데이터가 쌓일 때까지 방향 베팅보다 관찰이 우선입니다.",
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
    benchmark_history: list[dict] | None = None,
    macro_snapshot: dict | None = None,
    kosis_snapshot: dict | None = None,
    fundamental_context: dict | None = None,
    filings: list[dict] | None = None,
    event_context: dict | None = None,
    breadth_context: dict | None = None,
) -> NextDayForecast:
    del context_bias  # Legacy compatibility: the new engine is numeric-first.

    if not price_history:
        return _fallback_forecast(ticker, country_code, 0.0, datetime.now().date().isoformat())

    reference_date = str(price_history[-1].get("date") or datetime.now().date().isoformat())
    current_price = float(price_history[-1].get("close") or 0.0)

    distribution = build_distributional_forecast(
        price_history=price_history,
        benchmark_history=benchmark_history,
        macro_snapshot=macro_snapshot,
        kosis_snapshot=kosis_snapshot,
        analyst_context=analyst_context,
        fundamental_context=fundamental_context,
        flow_signal=flow_signal,
        news_items=news_items,
        filings=filings,
        event_context=event_context,
        breadth_context=breadth_context,
        horizons=(1,),
        asset_type=asset_type,
    )
    if distribution is None:
        return _fallback_forecast(ticker, country_code, current_price, reference_date)

    horizon = distribution.horizons[1]
    target_date = next_trading_day(country_code, distribution.reference_date).isoformat()
    direction = max(
        {
            "up": horizon.p_up,
            "flat": horizon.p_flat,
            "down": horizon.p_down,
        },
        key=lambda key: {
            "up": horizon.p_up,
            "flat": horizon.p_flat,
            "down": horizon.p_down,
        }[key],
    )
    predicted_return_pct = horizon.q50 * 100.0
    execution_bias, execution_note = _build_execution_bias(
        direction=direction,
        up_probability=horizon.p_up,
        confidence=horizon.confidence,
        predicted_return_pct=predicted_return_pct,
        regime=distribution.regime,
    )

    scenarios = [
        ForecastScenario(
            name="Bull",
            price=_price_from_return(distribution.reference_price, horizon.q90),
            probability=round(horizon.p_up, 1),
            description="상방 tail 확률을 반영한 90분위 가격입니다.",
        ),
        ForecastScenario(
            name="Base",
            price=_price_from_return(distribution.reference_price, horizon.q50),
            probability=round(horizon.p_flat, 1),
            description="조건부 수익률 분포의 중앙값(q50)입니다.",
        ),
        ForecastScenario(
            name="Bear",
            price=_price_from_return(distribution.reference_price, horizon.q10),
            probability=round(horizon.p_down, 1),
            description="하방 tail 확률을 반영한 10분위 가격입니다.",
        ),
    ]

    risk_flags = _build_risk_flags(
        regime=distribution.regime,
        q10=horizon.q10,
        q90=horizon.q90,
        event_uncertainty=distribution.event_features.uncertainty,
        confidence=horizon.confidence,
    )
    note = (
        f"{name}의 다음 거래일 예측은 다중 기간 가격 인코더와 Student-t mixture 분포를 사용합니다. "
        f"{distribution.confidence_note}"
    )

    return NextDayForecast(
        target_date=target_date,
        reference_date=distribution.reference_date,
        reference_price=round(distribution.reference_price, 2),
        direction=direction,
        up_probability=round(horizon.p_up, 2),
        predicted_open=round(_price_from_return(distribution.reference_price, horizon.q50 * 0.35), 2),
        predicted_close=_price_from_return(distribution.reference_price, horizon.q50),
        predicted_high=_price_from_return(distribution.reference_price, horizon.q90),
        predicted_low=_price_from_return(distribution.reference_price, horizon.q10),
        predicted_return_pct=round(predicted_return_pct, 2),
        confidence=round(horizon.confidence, 2),
        raw_confidence=round(float(horizon.raw_confidence or horizon.confidence), 2),
        calibrated_probability=round(float(horizon.calibrated_probability or (horizon.confidence / 100.0)), 4),
        probability_edge=round(float(horizon.probability_edge or 0.0), 4),
        analog_support=horizon.analog_support,
        regime_support=horizon.regime_support,
        agreement_support=horizon.agreement_support,
        data_quality_support=horizon.data_quality_support,
        volatility_ratio=horizon.volatility_ratio,
        confidence_calibrator=horizon.confidence_calibrator,
        calibration_snapshot=horizon.calibration_snapshot,
        confidence_note=note,
        news_sentiment=round(distribution.event_features.sentiment, 3),
        raw_signal=round(distribution.raw_signal, 4),
        scenarios=scenarios,
        risk_flags=risk_flags,
        execution_bias=execution_bias,
        execution_note=execution_note,
        flow_signal=flow_signal,
        drivers=_map_drivers(distribution.evidence),
        model_version=MODEL_VERSION,
    )
