import asyncio
from datetime import datetime, timezone
from importlib import import_module
import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import SP_5011, SP_5012, SP_5018
from app.runtime import get_runtime_state
from app.utils.lazy_module import LazyModuleProxy
from app.utils.memory_hygiene import get_memory_pressure_snapshot, maybe_trim_process_memory
from app.utils.route_trace import build_route_trace

router = APIRouter(prefix="/api", tags=["briefing"])
settings = get_settings()
market_session_service = LazyModuleProxy("app.services.market_session_service")
route_stability_service = LazyModuleProxy("app.services.route_stability_service")
log = logging.getLogger("stock_predict.briefing_route")
PUBLIC_ENDPOINT_TIMEOUT_SECONDS = 6.0
PUBLIC_FAST_FALLBACK_PRESSURE_RATIO = 0.8
PUBLIC_STARTUP_GUARD_SECONDS = 300


def _maybe_trim_public_route_memory(reason: str) -> None:
    try:
        maybe_trim_process_memory(reason)
    except Exception:
        pass


async def _run_deferred_public_route_memory_trim(reason: str) -> None:
    await asyncio.to_thread(_maybe_trim_public_route_memory, reason)


def _schedule_public_route_memory_trim(reason: str | None) -> None:
    if not reason:
        return
    try:
        asyncio.create_task(_run_deferred_public_route_memory_trim(reason))
    except RuntimeError:
        _maybe_trim_public_route_memory(reason)


def _public_memory_pressure_ratio() -> float:
    try:
        snapshot = get_memory_pressure_snapshot()
    except Exception:
        return 0.0
    return float(snapshot.get("pressure_ratio") or 0.0)


async def _load_daily_briefing_payload() -> dict:
    module = await asyncio.to_thread(import_module, "app.services.briefing_service")
    return await module.get_daily_briefing()


def _observe_briefing_task(task: asyncio.Task, label: str) -> None:
    def _consume_result(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log.warning("Daily briefing %s finished with a late failure: %s", label, exc, exc_info=True)

    task.add_done_callback(_consume_result)


def _should_use_ultra_fast_public_fallback() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    return _public_memory_pressure_ratio() >= PUBLIC_FAST_FALLBACK_PRESSURE_RATIO


def _should_use_startup_public_route_guard() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    try:
        runtime_state = get_runtime_state()
        started_at_raw = str(runtime_state.get("started_at") or "").strip()
        if not started_at_raw:
            return False
        started_at = datetime.fromisoformat(started_at_raw)
        now = datetime.now(started_at.tzinfo or timezone.utc)
        return (now - started_at).total_seconds() <= PUBLIC_STARTUP_GUARD_SECONDS
    except Exception:
        return False


def _build_daily_briefing_shell(note: str, *, fallback_reason: str = "briefing_timeout") -> dict:
    return {
        "generated_at": datetime.now().isoformat(),
        "partial": True,
        "fallback_reason": fallback_reason,
        "sessions": [],
        "market_view": [
            {
                "country_code": "KR",
                "label": "브리핑 지연",
                "stance": "neutral",
                "conviction": 0.0,
                "actionable_count": 0,
                "bullish_count": 0,
                "summary": note,
            }
        ],
        "focus_cards": [],
        "upcoming_events": [],
        "research_archive": {
            "todays_reports": 0,
            "total_reports": 0,
            "source_count": 0,
            "last_synced_at": None,
        },
        "priorities": [
            note,
            "브리핑 상세는 같은 화면을 다시 열거나 잠시 뒤 새로고침하면 순차적으로 다시 채워집니다.",
        ],
    }


@router.get("/briefing/daily")
async def get_daily_briefing():
    started_at = time.perf_counter()
    pressure_guard = _should_use_ultra_fast_public_fallback()
    startup_guard = _should_use_startup_public_route_guard()
    if pressure_guard or startup_guard:
        payload = _build_daily_briefing_shell(
            "브리핑 전체 계산을 잠시 건너뛰고 지금은 세션 상태와 핵심 일정만 먼저 표시합니다."
        )
        route_stability_service.record_route_trace(
            "daily_briefing",
            build_route_trace(
                route_key="daily_briefing",
                request_phase="shell",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                timeout_budget_ms=PUBLIC_ENDPOINT_TIMEOUT_SECONDS * 1000.0,
                upstream_source="briefing_service",
                payload=payload,
                fallback_reason="daily_briefing_memory_guard" if pressure_guard else "daily_briefing_startup_guard",
                served_state="partial",
            ),
        )
        _schedule_public_route_memory_trim("daily_briefing")
        return payload
    briefing_task: asyncio.Task | None = None
    try:
        briefing_task = asyncio.create_task(_load_daily_briefing_payload())
        payload = await asyncio.wait_for(
            asyncio.shield(briefing_task),
            timeout=PUBLIC_ENDPOINT_TIMEOUT_SECONDS,
        )
        route_stability_service.record_route_trace(
            "daily_briefing",
            build_route_trace(
                route_key="daily_briefing",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                timeout_budget_ms=PUBLIC_ENDPOINT_TIMEOUT_SECONDS * 1000.0,
                upstream_source="briefing_service",
                payload=payload,
            ),
        )
        _schedule_public_route_memory_trim("daily_briefing")
        return payload
    except asyncio.TimeoutError:
        if briefing_task is not None:
            _observe_briefing_task(briefing_task, "full")
        err = SP_5018(f"Daily briefing exceeded {PUBLIC_ENDPOINT_TIMEOUT_SECONDS} seconds.")
        err.log("warning")
        payload = _build_daily_briefing_shell(
            "브리핑 전체 계산이 길어져 지금은 세션 상태와 핵심 일정만 먼저 표시합니다."
        )
        route_stability_service.record_route_trace(
            "daily_briefing",
            build_route_trace(
                route_key="daily_briefing",
                request_phase="shell",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                timeout_budget_ms=PUBLIC_ENDPOINT_TIMEOUT_SECONDS * 1000.0,
                upstream_source="briefing_service",
                payload=payload,
                fallback_reason="daily_briefing_timeout",
            ),
        )
        _schedule_public_route_memory_trim("daily_briefing")
        return payload
    except asyncio.CancelledError:
        if briefing_task is not None:
            briefing_task.cancel()
        raise
    except Exception as exc:
        err = SP_5011(str(exc)[:200])
        err.log()
        payload = _build_daily_briefing_shell(
            "브리핑 계산 중 오류가 발생해 지금은 세션 상태와 핵심 일정만 먼저 표시합니다."
        )
        route_stability_service.record_route_trace(
            "daily_briefing",
            build_route_trace(
                route_key="daily_briefing",
                request_phase="shell",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                timeout_budget_ms=PUBLIC_ENDPOINT_TIMEOUT_SECONDS * 1000.0,
                upstream_source="briefing_service",
                payload=payload,
                fallback_reason="daily_briefing_error",
                served_state="partial",
            ),
        )
        _schedule_public_route_memory_trim("daily_briefing")
        return payload


@router.get("/market/sessions")
async def get_market_sessions():
    started_at = time.perf_counter()
    try:
        payload = await market_session_service.get_market_sessions()
        route_stability_service.record_route_trace(
            "market_sessions",
            build_route_trace(
                route_key="market_sessions",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                upstream_source="market_session_service",
                payload=payload,
            ),
        )
        _maybe_trim_public_route_memory("market_sessions")
        return payload
    except Exception as exc:
        err = SP_5012(str(exc)[:200])
        err.log()
        route_stability_service.record_route_trace(
            "market_sessions",
            build_route_trace(
                route_key="market_sessions",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                upstream_source="market_session_service",
                fallback_reason="market_sessions_error",
                served_state="degraded",
            ),
        )
        _maybe_trim_public_route_memory("market_sessions")
        return JSONResponse(status_code=500, content=err.to_dict())
