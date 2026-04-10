import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.auth import AuthenticatedUser, get_current_user
from app.errors import SP_5003, SP_6017
from app.utils.lazy_module import LazyModuleProxy
from app.utils.route_trace import build_route_trace

router = APIRouter(prefix="/api", tags=["watchlist"])
route_stability_service = LazyModuleProxy("app.services.route_stability_service")
watchlist_service = LazyModuleProxy("app.services.watchlist_service")
watchlist_tracking_service = LazyModuleProxy("app.services.watchlist_tracking_service")


def _record_watchlist_write_trace(
    *,
    route_key: str = "watchlist",
    action: str,
    started_at: float,
    served_state: str = "fresh",
    fallback_reason: str | None = None,
    failure_class: str | None = None,
    panel_key: str = "watchlist_mutation",
):
    route_stability_service.record_route_trace(
        route_key,
        build_route_trace(
            route_key=route_key,
            request_phase="full",
            cache_state="miss",
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            upstream_source=f"watchlist_service:{action}",
            served_state=served_state,
            fallback_reason=fallback_reason,
            operation_kind="auth-write",
            failure_class=failure_class,
            panel_key=panel_key,
            dependency_key="supabase",
        ),
    )


def _record_watchlist_read_trace(
    *,
    route_key: str,
    started_at: float,
    upstream_source: str,
    payload: dict | list | None = None,
    served_state: str = "fresh",
    fallback_reason: str | None = None,
    failure_class: str | None = None,
    panel_key: str | None = None,
):
    route_stability_service.record_route_trace(
        route_key,
        build_route_trace(
            route_key=route_key,
            request_phase="full",
            cache_state="miss",
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            upstream_source=upstream_source,
            payload=payload,
            served_state=served_state,
            fallback_reason=fallback_reason,
            operation_kind="auth-read",
            failure_class=failure_class,
            panel_key=panel_key,
            dependency_key="supabase",
        ),
    )


@router.get("/watchlist")
async def get_watchlist(current_user: AuthenticatedUser = Depends(get_current_user)):
    started_at = time.perf_counter()
    try:
        payload = await watchlist_service.get_watchlist(current_user.id)
        _record_watchlist_read_trace(
            route_key="watchlist",
            started_at=started_at,
            upstream_source="watchlist_service",
            payload=payload,
            panel_key="watchlist_items",
        )
        return payload
    except Exception as e:
        err = SP_5003(f"list: {e}")
        err.log()
        _record_watchlist_read_trace(
            route_key="watchlist",
            started_at=started_at,
            upstream_source="watchlist_service",
            served_state="degraded",
            fallback_reason="watchlist_error",
            panel_key="watchlist_items",
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/watchlist/{ticker}")
async def add_watchlist(
    ticker: str,
    country_code: str = "KR",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    started_at = time.perf_counter()
    try:
        resolution = await watchlist_service.add_to_watchlist(current_user.id, ticker, country_code)
        _record_watchlist_write_trace(action="add", started_at=started_at)
        return {"status": "added", "ticker": resolution["ticker"], "country_code": resolution["country_code"], "note": resolution["note"]}
    except Exception as e:
        err = SP_5003(f"add({ticker}): {e}")
        err.log()
        _record_watchlist_write_trace(
            action="add",
            started_at=started_at,
            served_state="degraded",
            fallback_reason="watchlist_write_error",
            failure_class="write_failed",
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    started_at = time.perf_counter()
    try:
        await watchlist_service.remove_from_watchlist(current_user.id, ticker)
        _record_watchlist_write_trace(action="remove", started_at=started_at)
        return {"status": "removed", "ticker": ticker}
    except Exception as e:
        err = SP_5003(f"remove({ticker}): {e}")
        err.log()
        _record_watchlist_write_trace(
            action="remove",
            started_at=started_at,
            served_state="degraded",
            fallback_reason="watchlist_write_error",
            failure_class="write_failed",
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/watchlist/{ticker}/tracking")
async def enable_watchlist_tracking(
    ticker: str,
    country_code: str = "KR",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    started_at = time.perf_counter()
    try:
        payload = await watchlist_tracking_service.set_tracking_enabled(current_user.id, ticker, country_code, True)
        if not payload:
            err = SP_6017(f"{ticker} is not in the current user's watchlist.")
            err.log("warning")
            _record_watchlist_write_trace(
                route_key="watchlist_detail",
                action="enable_tracking",
                started_at=started_at,
                served_state="degraded",
                fallback_reason="watchlist_item_missing",
                failure_class="contract_mismatch",
                panel_key="watchlist_tracking",
            )
            return JSONResponse(status_code=404, content=err.to_dict())
        _record_watchlist_write_trace(
            route_key="watchlist_detail",
            action="enable_tracking",
            started_at=started_at,
            panel_key="watchlist_tracking",
        )
        return {
            "status": "tracking_enabled",
            "ticker": payload["ticker"],
            "country_code": payload["country_code"],
            "tracking_enabled": True,
            "tracking_started_at": payload.get("tracking_started_at"),
            "tracking_updated_at": payload.get("tracking_updated_at"),
        }
    except Exception as e:
        err = SP_5003(f"tracking_on({ticker}): {e}")
        err.log()
        _record_watchlist_write_trace(
            route_key="watchlist_detail",
            action="enable_tracking",
            started_at=started_at,
            served_state="degraded",
            fallback_reason="watchlist_write_error",
            failure_class="write_failed",
            panel_key="watchlist_tracking",
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.delete("/watchlist/{ticker}/tracking")
async def disable_watchlist_tracking(
    ticker: str,
    country_code: str = "KR",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    started_at = time.perf_counter()
    try:
        payload = await watchlist_tracking_service.set_tracking_enabled(current_user.id, ticker, country_code, False)
        if not payload:
            err = SP_6017(f"{ticker} is not in the current user's watchlist.")
            err.log("warning")
            _record_watchlist_write_trace(
                route_key="watchlist_detail",
                action="disable_tracking",
                started_at=started_at,
                served_state="degraded",
                fallback_reason="watchlist_item_missing",
                failure_class="contract_mismatch",
                panel_key="watchlist_tracking",
            )
            return JSONResponse(status_code=404, content=err.to_dict())
        _record_watchlist_write_trace(
            route_key="watchlist_detail",
            action="disable_tracking",
            started_at=started_at,
            panel_key="watchlist_tracking",
        )
        return {
            "status": "tracking_disabled",
            "ticker": payload["ticker"],
            "country_code": payload["country_code"],
            "tracking_enabled": False,
            "tracking_started_at": payload.get("tracking_started_at"),
            "tracking_updated_at": payload.get("tracking_updated_at"),
        }
    except Exception as e:
        err = SP_5003(f"tracking_off({ticker}): {e}")
        err.log()
        _record_watchlist_write_trace(
            route_key="watchlist_detail",
            action="disable_tracking",
            started_at=started_at,
            served_state="degraded",
            fallback_reason="watchlist_write_error",
            failure_class="write_failed",
            panel_key="watchlist_tracking",
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/watchlist/{ticker}/tracking-detail")
async def get_watchlist_tracking_detail(
    ticker: str,
    country_code: str = "KR",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    started_at = time.perf_counter()
    try:
        payload = await watchlist_tracking_service.get_tracking_detail(current_user.id, ticker, country_code)
        if not payload:
            err = SP_6017(f"{ticker} is not in the current user's watchlist.")
            err.log("warning")
            _record_watchlist_read_trace(
                route_key="watchlist_detail",
                started_at=started_at,
                upstream_source="watchlist_tracking_service",
                served_state="degraded",
                fallback_reason="watchlist_item_missing",
                failure_class="contract_mismatch",
                panel_key="watchlist_tracking_detail",
            )
            return JSONResponse(status_code=404, content=err.to_dict())
        _record_watchlist_read_trace(
            route_key="watchlist_detail",
            started_at=started_at,
            upstream_source="watchlist_tracking_service",
            payload=payload,
            served_state="partial" if payload.get("partial") else "fresh",
            fallback_reason=payload.get("fallback_reason"),
            panel_key="watchlist_tracking_detail",
        )
        return payload
    except Exception as e:
        err = SP_5003(f"tracking_detail({ticker}): {e}")
        err.log()
        _record_watchlist_read_trace(
            route_key="watchlist_detail",
            started_at=started_at,
            upstream_source="watchlist_tracking_service",
            served_state="degraded",
            fallback_reason="watchlist_tracking_error",
            failure_class="panel_fetch_failed",
            panel_key="watchlist_tracking_detail",
        )
        return JSONResponse(status_code=500, content=err.to_dict())
