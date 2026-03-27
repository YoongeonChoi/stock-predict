"""Free-data KR probabilistic forecast backed by the shared distribution engine."""

from __future__ import annotations

from app.analysis.distributional_return_engine import MODEL_VERSION, build_distributional_forecast
from app.config import get_settings
from app.models.forecast import (
    FlowSignal,
    FreeKrForecast,
    FreeKrForecastDataSource,
    FreeKrForecastEvidence,
    FreeKrForecastHorizon,
)
from app.utils.market_calendar import trading_days_forward

HORIZONS = (1, 5, 20)


def _signal_label(value: float) -> str:
    if value > 0.05:
        return "bullish"
    if value < -0.05:
        return "bearish"
    return "neutral"


def _price(reference_price: float, log_return: float) -> float:
    from math import exp

    return round(reference_price * exp(log_return), 2) if reference_price > 0 else 0.0


def _data_sources(
    *,
    google_news: list[dict],
    naver_news: list[dict],
    filings: list[dict],
    ecos_snapshot: dict,
    kosis_snapshot: dict,
    flow_signal: FlowSignal | None,
) -> list[FreeKrForecastDataSource]:
    settings = get_settings()
    return [
        FreeKrForecastDataSource(
            name="Yahoo Finance",
            configured=True,
            used=True,
            item_count=1,
            note="가격·거래량·지수 입력의 기본 백본입니다.",
        ),
        FreeKrForecastDataSource(
            name="Google News RSS",
            configured=True,
            used=bool(google_news),
            item_count=len(google_news),
            note="헤드라인 기반 단기 이벤트 보조 신호입니다.",
        ),
        FreeKrForecastDataSource(
            name="Naver Search API",
            configured=bool(settings.naver_client_id and settings.naver_client_secret),
            used=bool(naver_news),
            item_count=len(naver_news),
            note="국내 뉴스 메타데이터 보강용입니다.",
        ),
        FreeKrForecastDataSource(
            name="OpenDART",
            configured=bool(settings.opendart_api_key),
            used=bool(filings),
            item_count=len(filings),
            note="주요사항보고·공시 이벤트를 보조 신호로 반영합니다.",
        ),
        FreeKrForecastDataSource(
            name="ECOS",
            configured=bool(settings.ecos_api_key),
            used=bool(ecos_snapshot),
            item_count=len([value for value in ecos_snapshot.values() if value is not None]),
            note="공개시차 안전 거시 요인 압축 입력입니다.",
        ),
        FreeKrForecastDataSource(
            name="KOSIS",
            configured=bool(settings.kosis_api_key),
            used=bool(kosis_snapshot),
            item_count=len([value for value in kosis_snapshot.values() if value is not None]),
            note="고용·생산 등 정부 통계를 ECOS와 함께 압축합니다.",
        ),
        FreeKrForecastDataSource(
            name="PyKRX Investor Flow",
            configured=True,
            used=bool(flow_signal and flow_signal.available),
            item_count=1 if flow_signal and flow_signal.available else 0,
            note="외국인·기관 수급을 선택적 게이트로 반영합니다.",
        ),
    ]


def build_free_kr_forecast(
    *,
    ticker: str,
    name: str,
    price_history: list[dict],
    market_history: list[dict],
    google_news: list[dict] | None = None,
    naver_news: list[dict] | None = None,
    filings: list[dict] | None = None,
    flow_signal: FlowSignal | None = None,
    analyst_context: dict | None = None,
    ecos_snapshot: dict | None = None,
    kosis_snapshot: dict | None = None,
    fundamental_context: dict | None = None,
    event_context: dict | None = None,
):
    google_news = google_news or []
    naver_news = naver_news or []
    filings = filings or []
    ecos_snapshot = ecos_snapshot or {}
    kosis_snapshot = kosis_snapshot or {}

    distribution = build_distributional_forecast(
        price_history=price_history,
        benchmark_history=market_history,
        macro_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
        analyst_context=analyst_context or {},
        fundamental_context=fundamental_context or {},
        flow_signal=flow_signal,
        news_items=[*google_news, *naver_news],
        filings=filings,
        event_context=event_context,
        horizons=HORIZONS,
        asset_type="stock",
    )
    if distribution is None:
        return None

    target_dates = trading_days_forward("KR", distribution.reference_date, max(HORIZONS))
    horizons: list[FreeKrForecastHorizon] = []
    for horizon_days in HORIZONS:
        horizon = distribution.horizons[horizon_days]
        horizons.append(
            FreeKrForecastHorizon(
                horizon_days=horizon_days,
                target_date=(
                    target_dates[horizon_days - 1].isoformat()
                    if len(target_dates) >= horizon_days
                    else distribution.reference_date
                ),
                mean_return_raw=horizon.mean_return_raw,
                mean_return_excess=horizon.mean_return_excess,
                q10=horizon.q10,
                q25=horizon.q25,
                q50=horizon.q50,
                q75=horizon.q75,
                q90=horizon.q90,
                price_q10=_price(distribution.reference_price, horizon.q10),
                price_q25=_price(distribution.reference_price, horizon.q25),
                price_q50=_price(distribution.reference_price, horizon.q50),
                price_q75=_price(distribution.reference_price, horizon.q75),
                price_q90=_price(distribution.reference_price, horizon.q90),
                p_down=horizon.p_down,
                p_flat=horizon.p_flat,
                p_up=horizon.p_up,
                vol_forecast=horizon.vol_forecast,
                confidence=horizon.confidence,
                raw_confidence=horizon.raw_confidence,
                calibrated_probability=horizon.calibrated_probability,
                probability_edge=horizon.probability_edge,
                analog_support=horizon.analog_support,
                regime_support=horizon.regime_support,
                agreement_support=horizon.agreement_support,
                data_quality_support=horizon.data_quality_support,
                volatility_ratio=horizon.volatility_ratio,
                confidence_calibrator=horizon.confidence_calibrator,
            )
        )

    evidence = [
        FreeKrForecastEvidence(
            key=item.key,
            label=item.label,
            contribution=round(item.contribution, 4),
            signal=_signal_label(item.contribution),
            detail=item.detail,
        )
        for item in distribution.evidence
    ]

    data_sources = _data_sources(
        google_news=google_news,
        naver_news=naver_news,
        filings=filings,
        ecos_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
        flow_signal=flow_signal,
    )
    summary = (
        f"{name}의 무료 KR 확률 엔진입니다. 가격·변동성·상대강도 같은 수치 시계열을 주신호로 두고, "
        "거시·공시·뉴스는 게이트 결합으로 보정합니다."
    )

    return FreeKrForecast(
        reference_date=distribution.reference_date,
        reference_price=round(distribution.reference_price, 2),
        regime=distribution.regime,
        regime_probs=distribution.regime_probs,
        horizons=horizons,
        evidence=evidence,
        data_sources=data_sources,
        confidence_note=distribution.confidence_note,
        summary=summary,
        model_version=MODEL_VERSION,
    )
