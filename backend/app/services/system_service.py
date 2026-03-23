"""System diagnostics and readiness summary."""

from __future__ import annotations

from app.analysis.historical_pattern_forecast import MODEL_VERSION as HISTORICAL_MODEL_VERSION
from app.analysis.next_day_forecast import MODEL_VERSION
from app.config import get_settings
from app.runtime import get_runtime_state
from app.services import archive_service, research_archive_service
from app.version import APP_VERSION


def _configured(value: str) -> bool:
    return bool(str(value or "").strip())


def _source(name: str, configured: bool, purpose: str, note: str, status: str | None = None) -> dict:
    resolved_status = status or ("configured" if configured else "missing")
    return {
        "name": name,
        "configured": configured,
        "status": resolved_status,
        "purpose": purpose,
        "note": note,
    }


async def get_diagnostics() -> dict:
    settings = get_settings()
    runtime_state = get_runtime_state()

    accuracy = None
    accuracy_error = None
    research_archive = None
    research_archive_error = None
    try:
        accuracy = await archive_service.get_accuracy(refresh=False)
    except Exception as exc:
        accuracy_error = str(exc)

    try:
        research_archive = await research_archive_service.get_public_research_status(
            refresh_if_missing=False
        )
    except Exception as exc:
        research_archive_error = str(exc)

    data_sources = [
        _source(
            "OpenAI",
            _configured(settings.openai_api_key),
            "서술형 요약과 기관 관점 합성",
            "키가 없어도 앱은 동작하지만 설명 품질과 서술 깊이는 낮아집니다.",
        ),
        _source(
            "Financial Modeling Prep",
            _configured(settings.fmp_api_key),
            "스크리너, 피어 비교, 애널리스트 컨텍스트, 시장 캘린더",
            "응답이 없으면 더 작은 유니버스와 Yahoo 기반 대체 흐름으로 동작합니다.",
        ),
        _source(
            "FRED",
            _configured(settings.fred_api_key),
            "미국 매크로와 금리 컨텍스트",
            "미설정 시 미국 국가 분석의 거시 입력이 약해집니다.",
        ),
        _source(
            "ECOS",
            _configured(settings.ecos_api_key),
            "한국 매크로 데이터",
            "미설정 시 한국 국가 분석의 거시 입력이 약해집니다.",
        ),
        _source(
            "Yahoo Finance",
            True,
            "핵심 가격 이력, 지수 수준, 기본 펀더멘털",
            "실행 시점의 가격 시계열을 책임지는 기본 백본입니다.",
            status="available",
        ),
        _source(
            "PyKRX",
            True,
            "한국 외국인/기관 수급 보조 입력",
            "한국 시장에서만 사용하며 데이터가 비면 모델이 자동으로 중립 처리합니다.",
            status="best_effort",
        ),
        _source(
            "공식 기관 리서치 아카이브",
            True,
            "Fed·KDI·한국은행·BOJ·BIS 공식 리포트 큐레이션",
            "하루 한 번 동기화하며 PDF가 있으면 바로 연결하고, 없으면 원문 링크를 제공합니다.",
            status="available" if research_archive else "best_effort",
        ),
    ]

    status = runtime_state["status"]
    if (accuracy_error or research_archive_error) and status == "ok":
        status = "degraded"

    return {
        "status": status,
        "version": APP_VERSION,
        "started_at": runtime_state["started_at"],
        "startup_tasks": runtime_state["startup_tasks"],
        "data_sources": data_sources,
        "forecast_models": [
            {
                "name": "next_day",
                "version": MODEL_VERSION,
                "markets": ["US", "KR", "JP"],
                "signals": [
                    "trend_momentum",
                    "ema_alignment",
                    "mean_reversion",
                    "macd_impulse",
                    "candle_control",
                    "volume_confirmation",
                    "localized_news_sentiment",
                    "regime_overlay",
                    "investor_flow_best_effort",
                    "bull_base_bear_scenarios",
                    "execution_bias",
                    "risk_flags",
                ],
                "notes": [
                    "한국 수급 데이터는 PyKRX 커버리지가 있는 구간에서 가장 강하게 작동합니다.",
                    "signal-v2.4부터 다음 거래일 예측은 상방/기준/하방 시나리오와 실행 바이어스를 함께 제공합니다.",
                    "예측 정확도 추적은 아카이브된 다음 거래일 예측을 기준으로 누적됩니다.",
                ],
            },
            {
                "name": "historical_pattern",
                "version": HISTORICAL_MODEL_VERSION,
                "markets": ["US", "KR", "JP"],
                "signals": [
                    "historical_analog_matching",
                    "multi_horizon_return_distribution",
                    "relative_strength_vs_market",
                    "setup_backtest",
                ],
                "notes": [
                    "최근 2년 가격 이력에서 현재와 비슷한 국면을 찾아 5·20·60거래일 기대 분포를 계산합니다.",
                    "유사 국면이 충분하지 않으면 이 모델은 조용히 생략되고 기존 다음 거래일 예측만 표시됩니다.",
                ],
            },
        ],
        "prediction_accuracy": accuracy,
        "prediction_accuracy_error": accuracy_error,
        "research_archive": research_archive,
        "research_archive_error": research_archive_error,
    }

