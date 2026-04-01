import asyncio
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.errors import SP_5011, SP_5012, SP_5018
from app.services import briefing_service, market_session_service, route_stability_service
from app.utils import build_route_trace

router = APIRouter(prefix="/api", tags=["briefing"])
PUBLIC_ENDPOINT_TIMEOUT_SECONDS = 12


@router.get("/briefing/daily")
async def get_daily_briefing():
    started_at = time.perf_counter()
    try:
        payload = await asyncio.wait_for(
            briefing_service.get_daily_briefing(),
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
        return payload
    except asyncio.TimeoutError:
        err = SP_5018(f"Daily briefing exceeded {PUBLIC_ENDPOINT_TIMEOUT_SECONDS} seconds.")
        err.log("warning")
        payload = await briefing_service.get_daily_briefing_fallback(
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
        return payload
    except Exception as exc:
        err = SP_5011(str(exc)[:200])
        err.log()
        payload = await briefing_service.get_daily_briefing_fallback(
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
        return JSONResponse(status_code=500, content=err.to_dict())
