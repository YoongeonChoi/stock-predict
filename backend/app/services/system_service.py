"""System diagnostics and readiness summary."""

from __future__ import annotations

from app.analysis.free_kr_forecast import MODEL_VERSION as FREE_KR_MODEL_VERSION
from app.analysis.historical_pattern_forecast import MODEL_VERSION as HISTORICAL_MODEL_VERSION
from app.analysis.next_day_forecast import MODEL_VERSION
from app.config import get_settings
from app.runtime import get_runtime_state
from app.services import archive_service, research_archive_service
from app.version import APP_VERSION


def _configured(value: str) -> bool:
    return bool(str(value or "").strip())


def _any_configured(*values: str) -> bool:
    return any(_configured(value) for value in values)


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
            "뉴스·보도자료·공시의 구조화 이벤트 추출과 서술형 요약",
            "키가 없어도 숫자 예측은 동작하지만 이벤트 구조화와 서술 품질은 낮아집니다.",
        ),
        _source(
            "Financial Modeling Prep",
            _configured(settings.fmp_api_key),
            "스크리너, 피어 비교, 애널리스트 컨텍스트, 시장 캘린더",
            "응답이 없으면 더 작은 유니버스와 Yahoo 기반 대체 흐름으로 동작합니다.",
        ),
        _source(
            "ECOS",
            _configured(settings.ecos_api_key),
            "한국 매크로 데이터",
            "미설정 시 한국 국가 분석의 거시 입력이 약해집니다.",
        ),
        _source(
            "OpenDART",
            _configured(settings.opendart_api_key),
            "최근 공시와 한국 상장사 이벤트 보강",
            "주요사항보고와 재무 공시를 중기 이벤트·펀더멘털 보조 신호로 사용합니다.",
        ),
        _source(
            "KOSIS",
            _configured(settings.kosis_api_key)
            and _any_configured(
                settings.kosis_cpi_stats_id,
                settings.kosis_employment_stats_id,
                settings.kosis_industrial_production_stats_id,
            ),
            "정부 통계 보강",
            "KOSIS API 키와 통계표 ID를 함께 넣어야 공개시차 안전 거시 요인 압축 입력으로 사용됩니다.",
        ),
        _source(
            "Naver Search API",
            _configured(settings.naver_client_id) and _configured(settings.naver_client_secret),
            "국내 뉴스 헤드라인 보강",
            "Google News RSS 대비 국내 기사 커버리지를 보강합니다.",
        ),
        _source(
            "Google News RSS",
            True,
            "한국장 뉴스 헤드라인 수집",
            "무료 헤드라인 기반이라 장문 원문과 이벤트 구조화는 향후 OpenDART·네이버 뉴스 보강이 필요합니다.",
            status="best_effort",
        ),
        _source(
            "Yahoo Finance",
            True,
            "핵심 가격 이력, 지수 수준, 기본 펀더멘털",
            "한국장 무료 스택의 핵심 가격 백본입니다.",
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
            "KDI·한국은행 공식 리포트 큐레이션",
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
                "markets": ["KR"],
                "signals": [
                    "multi_period_price_encoder",
                    "release_safe_macro_compression",
                    "fundamental_event_gated_fusion",
                    "regime_probabilities",
                    "student_t_mixture_distribution",
                    "q10_q25_q50_q75_q90",
                    "up_flat_down_probabilities",
                    "execution_bias",
                    "risk_flags",
                ],
                "notes": [
                    "가격·변동성·상대강도 같은 숫자 시계열이 주신호이고, 뉴스·공시는 보조 신호로만 게이트 결합합니다.",
                    "OpenAI는 수익률을 직접 예측하지 않고, 뉴스·보도자료·공시를 구조화 이벤트 벡터로 추출하는 데만 사용합니다.",
                    "다음 거래일 예측은 Bull/Base/Bear 시나리오와 실행 바이어스를 같은 분포 예측 결과에서 파생합니다.",
                    "표시 confidence는 raw support를 horizon별 bootstrap sigmoid calibrator로 보정한 값이라, 높게 보이기보다 실제 적중률과 맞도록 설계합니다.",
                ],
            },
            {
                "name": "historical_pattern",
                "version": HISTORICAL_MODEL_VERSION,
                "markets": ["KR"],
                "signals": [
                    "historical_analog_matching",
                    "multi_horizon_return_distribution",
                    "relative_strength_vs_market",
                    "setup_backtest",
                ],
                "notes": [
                    "최근 2년 가격 이력에서 현재와 비슷한 국면을 찾아 5·20·60거래일 기대 분포를 계산합니다.",
                    "유사 국면이 충분하지 않으면 이 모델은 조용히 생략되고 기존 다음 거래일 예측만 표시됩니다.",
                    "analog confidence는 weighted win rate, effective sample size, profit factor, dispersion을 함께 본 support score로 재정의했습니다.",
                ],
            },
            {
                "name": "free_kr_probabilistic",
                "version": FREE_KR_MODEL_VERSION,
                "markets": ["KR"],
                "signals": [
                    "multi_period_price_encoder",
                    "relative_strength",
                    "ecos_kosis_macro_factors",
                    "opendart_filing_events",
                    "naver_fmp_news_structured_events",
                    "availability_aware_gates",
                    "regime_probabilities",
                    "student_t_mixture_distribution",
                    "q10_q25_q50_q75_q90",
                    "up_flat_down_probabilities",
                ],
                "notes": [
                    "공개시차 안전 거시 압축, 이벤트 구조화, 분포 예측을 묶은 한국장 확률 엔진입니다.",
                    "OpenDART, Naver Search API, KOSIS는 설정되어 있을 때만 보조 입력으로 반영되고, 결측은 availability mask로 중립 처리합니다.",
                    "가격은 분위수, 방향은 up/flat/down 확률, 장세는 risk-on/neutral/risk-off 확률로 제공합니다.",
                ],
            },
        ],
        "prediction_accuracy": accuracy,
        "prediction_accuracy_error": accuracy_error,
        "research_archive": research_archive,
        "research_archive_error": research_archive_error,
    }

