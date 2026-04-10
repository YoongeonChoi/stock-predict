from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.errors import SP_5006
from app.utils.lazy_module import LazyModuleProxy

router = APIRouter(prefix="/api", tags=["system"])
route_stability_service = LazyModuleProxy("app.services.route_stability_service")
system_service = LazyModuleProxy("app.services.system_service")


class DiagnosticsEvent(BaseModel):
    route: str
    event: str
    status: str = "ok"
    panel: str | None = None
    panel_key: str | None = None
    detail: str | None = None
    failure_class: str | None = None
    operation_kind: str | None = None
    dependency_key: str | None = None
    recovered: bool | None = None
    timeout_ms: int | None = None
    occurred_at: str | None = None


@router.get("/diagnostics")
@router.get("/system/diagnostics")
async def diagnostics():
    try:
        return await system_service.get_diagnostics()
    except Exception as exc:
        err = SP_5006(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/diagnostics/event")
@router.post("/system/diagnostics/event")
async def diagnostics_event(body: DiagnosticsEvent):
    try:
        route_stability_service.record_frontend_event(
            route=body.route,
            event=body.event,
            status=body.status,
            panel=body.panel,
            panel_key=body.panel_key,
            detail=body.detail,
            failure_class=body.failure_class,
            operation_kind=body.operation_kind or "public-read",
            dependency_key=body.dependency_key,
            recovered=body.recovered,
            timeout_ms=body.timeout_ms,
            occurred_at=body.occurred_at,
        )
        return {"status": "ok"}
    except Exception as exc:
        err = SP_5006(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
