"""System diagnostics and readiness summary."""

from __future__ import annotations

import asyncio
import platform
try:
    import resource
except ImportError:  # pragma: no cover - Windows fallback
    resource = None

from app.analysis.free_kr_forecast import MODEL_VERSION as FREE_KR_MODEL_VERSION
from app.analysis.historical_pattern_forecast import MODEL_VERSION as HISTORICAL_MODEL_VERSION
from app.analysis.next_day_forecast import MODEL_VERSION
from app.config import get_settings
from app.data import cache as data_cache
from app.runtime import get_runtime_state
from app.services import (
    archive_service,
    confidence_calibration_service,
    learned_fusion_profile_service,
    research_archive_service,
    route_stability_service,
)
from app.utils.memory_hygiene import get_memory_trim_stats, maybe_trim_process_memory
from app.version import APP_VERSION

DIAGNOSTICS_HEAVY_PROBE_SKIP_PRESSURE_RATIO = 0.8


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


def _build_learned_fusion_status() -> dict:
    profile_rows = learned_fusion_profile_service.get_profile_summary()
    last_refresh_time = learned_fusion_profile_service.get_last_refresh_time()
    return {
        "active_model_version": MODEL_VERSION,
        "last_refresh_time": last_refresh_time,
        "graph_coverage_available": any(
            row.get("status") == "active" for row in profile_rows
        ),
        "horizons": [
            {
                "prediction_type": row.get("prediction_type"),
                "label": row.get("label"),
                "method": row.get("method") or "prior_only",
                "status": row.get("status") or "bootstrapping",
                "sample_count": int(row.get("sample_count") or 0),
                "prior_brier_delta": row.get("prior_brier_delta"),
                "fitted_at": row.get("fitted_at"),
            }
            for row in profile_rows
        ],
    }


def _empty_route_stability_summary() -> dict:
    return {
        "routes": [],
        "first_usable_metrics": {
            "tracked_routes": 0,
            "total_requests": 0,
            "p50_elapsed_ms": 0.0,
            "p95_elapsed_ms": 0.0,
            "fallback_served_rate": 0.0,
            "stale_served_rate": 0.0,
            "first_request_cold_failure_rate": 0.0,
            "blank_screen_rate": 0.0,
            "error_only_screen_rate": 0.0,
        },
        "hydration_failure_summary": {
            "tracked": False,
            "total": 0,
            "failure_count": 0,
            "failure_rate": 0.0,
            "by_route": [],
        },
        "session_recovery_summary": {
            "tracked": False,
            "total": 0,
            "failure_count": 0,
            "failure_rate": 0.0,
            "by_route": [],
        },
        "failure_class_summary": {
            "tracked": False,
            "total": 0,
            "by_class": {},
            "recovered_count": 0,
            "recovered_rate": 0.0,
        },
    }


def _consume_probe_task_result(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        return


async def _run_best_effort_probe(loader, *, timeout_seconds: int) -> tuple[object | None, str | None]:
    task = asyncio.create_task(loader())
    task.add_done_callback(_consume_probe_task_result)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), timeout=max(timeout_seconds, 1))
        return result, None
    except asyncio.TimeoutError:
        task.cancel()
        return None, f"timeout after {max(timeout_seconds, 1)}s"
    except Exception as exc:
        return None, str(exc)


def _read_int_file(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError:
        return None
    if not raw or raw == "max":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _get_process_memory_snapshot(settings) -> dict:
    rss_bytes = None
    peak_rss_bytes = None
    source = "unavailable"

    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            status_lines = handle.readlines()
        values: dict[str, int] = {}
        for line in status_lines:
            if ":" not in line:
                continue
            name, raw_value = line.split(":", 1)
            parts = raw_value.strip().split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].lower() == "kb":
                values[name] = int(parts[0]) * 1024
        rss_bytes = values.get("VmRSS")
        peak_rss_bytes = values.get("VmHWM")
        if rss_bytes is not None or peak_rss_bytes is not None:
            source = "proc_status"
    except OSError:
        pass

    if rss_bytes is None:
        try:
            if resource is None:
                raise RuntimeError("resource module unavailable")
            usage = resource.getrusage(resource.RUSAGE_SELF)
            factor = 1 if platform.system() == "Darwin" else 1024
            peak_rss_bytes = int(usage.ru_maxrss) * factor
            rss_bytes = peak_rss_bytes
            source = "resource"
        except Exception:
            pass

    cgroup_current_bytes = (
        _read_int_file("/sys/fs/cgroup/memory.current")
        or _read_int_file("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    )
    cgroup_limit_bytes = (
        _read_int_file("/sys/fs/cgroup/memory.max")
        or _read_int_file("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    )
    cache_stats = data_cache.get_memory_cache_stats()

    configured_budget_bytes = max(1, int(settings.runtime_memory_budget_mb)) * 1024 * 1024
    resolved_budget_bytes = cgroup_limit_bytes or configured_budget_bytes
    observed_bytes = cgroup_current_bytes or rss_bytes or 0
    pressure_ratio = (observed_bytes / resolved_budget_bytes) if resolved_budget_bytes else 0.0
    pressure_state = "ok"
    if pressure_ratio >= 0.9:
        pressure_state = "critical"
    elif pressure_ratio >= 0.75:
        pressure_state = "warning"

    return {
        "source": source,
        "rss_bytes": rss_bytes,
        "rss_mb": round((rss_bytes or 0) / (1024 * 1024), 2) if rss_bytes is not None else None,
        "peak_rss_bytes": peak_rss_bytes,
        "peak_rss_mb": round((peak_rss_bytes or 0) / (1024 * 1024), 2) if peak_rss_bytes is not None else None,
        "cgroup_current_bytes": cgroup_current_bytes,
        "cgroup_current_mb": round((cgroup_current_bytes or 0) / (1024 * 1024), 2) if cgroup_current_bytes is not None else None,
        "cgroup_limit_bytes": cgroup_limit_bytes,
        "cgroup_limit_mb": round((cgroup_limit_bytes or 0) / (1024 * 1024), 2) if cgroup_limit_bytes is not None else None,
        "configured_budget_mb": int(settings.runtime_memory_budget_mb),
        "resolved_budget_mb": round(resolved_budget_bytes / (1024 * 1024), 2) if resolved_budget_bytes else None,
        "pressure_ratio": round(pressure_ratio, 4),
        "pressure_state": pressure_state,
        "memory_cache": cache_stats,
        "memory_trim": get_memory_trim_stats(),
        "render_memory_safe_mode": bool(settings.startup_memory_safe_mode),
    }


async def get_diagnostics() -> dict:
    settings = get_settings()
    runtime_state = get_runtime_state()
    diagnostics_probe_timeout_seconds = max(
        1,
        int(
            getattr(
                settings,
                "effective_diagnostics_probe_timeout_seconds",
                getattr(settings, "diagnostics_probe_timeout_seconds", 3),
            )
        ),
    )

    preflight_memory_diagnostics = _get_process_memory_snapshot(settings)
    preflight_pressure_ratio = float(preflight_memory_diagnostics.get("pressure_ratio") or 0.0)
    preflight_pressure_state = str(preflight_memory_diagnostics.get("pressure_state") or "ok")

    if preflight_pressure_ratio >= 0.75:
        try:
            maybe_trim_process_memory("diagnostics_preflight")
        except Exception:
            pass
        preflight_memory_diagnostics = _get_process_memory_snapshot(settings)
        preflight_pressure_ratio = float(preflight_memory_diagnostics.get("pressure_ratio") or 0.0)
        preflight_pressure_state = str(preflight_memory_diagnostics.get("pressure_state") or "ok")

    if preflight_pressure_ratio >= DIAGNOSTICS_HEAVY_PROBE_SKIP_PRESSURE_RATIO:
        accuracy, accuracy_error = None, f"skipped under {preflight_pressure_state} memory pressure"
        research_archive, research_archive_error = None, f"skipped under {preflight_pressure_state} memory pressure"
    else:
        probe_timeout_seconds = diagnostics_probe_timeout_seconds
        if preflight_pressure_ratio >= 0.75:
            probe_timeout_seconds = min(probe_timeout_seconds, 1)
        (accuracy, accuracy_error), (research_archive, research_archive_error) = await asyncio.gather(
            _run_best_effort_probe(
                lambda: archive_service.get_accuracy(refresh=False),
                timeout_seconds=probe_timeout_seconds,
            ),
            _run_best_effort_probe(
                lambda: research_archive_service.get_public_research_status(refresh_if_missing=False),
                timeout_seconds=probe_timeout_seconds,
            ),
        )
    calibration_profiles = None
    try:
        calibration_profiles = confidence_calibration_service.get_profile_summary()
    except Exception:
        calibration_profiles = None

    try:
        learned_fusion_status = _build_learned_fusion_status()
    except Exception:
        learned_fusion_status = None
    try:
        route_stability_summary = route_stability_service.get_route_stability_summary()
    except Exception:
        route_stability_summary = _empty_route_stability_summary()

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
    memory_diagnostics = _get_process_memory_snapshot(settings)

    return {
        "status": status,
        "version": APP_VERSION,
        "started_at": runtime_state["started_at"],
        "render_memory_safe_mode": bool(settings.startup_memory_safe_mode),
        "startup_tasks": runtime_state["startup_tasks"],
        "memory_diagnostics": memory_diagnostics,
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
                    "learned_fusion_blending",
                    "lightweight_graph_context",
                    "q10_q25_q50_q75_q90",
                    "up_flat_down_probabilities",
                    "execution_bias",
                    "risk_flags",
                ],
                "notes": [
                    "가격·변동성·상대강도 같은 숫자 시계열이 주신호이고, 뉴스·공시는 보조 신호로만 게이트 결합합니다.",
                    "OpenAI는 수익률을 직접 예측하지 않고, 뉴스·보도자료·공시를 구조화 이벤트 벡터로 추출하는 데만 사용합니다.",
                    "다음 거래일 예측은 Bull/Base/Bear 시나리오와 실행 바이어스를 같은 분포 예측 결과에서 파생합니다.",
                    "prior backbone은 그대로 유지하고, 실측 prediction log가 충분한 horizon만 learned fusion과 경량 graph context를 추가해 보강합니다.",
                    "표시 confidence는 raw support를 bootstrap prior로 시작한 empirical calibrator가 실측 로그 기준으로 다시 맞춘 값이며, 표본이 충분해지면 isotonic 단계와 reliability bin까지 함께 갱신해 실제 적중률과 더 가깝게 맞춥니다.",
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
        "confidence_calibration_profiles": calibration_profiles,
        "learned_fusion_status": learned_fusion_status,
<<<<<<< HEAD
        "route_stability": runtime_state.get("route_stability", []),
=======
        "route_stability_summary": route_stability_summary["routes"],
        "first_usable_metrics": route_stability_summary["first_usable_metrics"],
        "hydration_failure_summary": route_stability_summary["hydration_failure_summary"],
        "session_recovery_summary": route_stability_summary["session_recovery_summary"],
        "failure_class_summary": route_stability_summary["failure_class_summary"],
>>>>>>> main
        "prediction_accuracy": accuracy,
        "prediction_accuracy_error": accuracy_error,
        "research_archive": research_archive,
        "research_archive_error": research_archive_error,
    }

