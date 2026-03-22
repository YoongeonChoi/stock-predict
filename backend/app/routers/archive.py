from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.errors import SP_5009, SP_6005, SP_6008
from app.services import archive_service, research_archive_service

router = APIRouter(prefix="/api", tags=["archive"])


@router.get("/archive")
async def list_archives(
    report_type: str | None = None,
    country_code: str | None = None,
    limit: int = Query(50, le=200),
):
    return await archive_service.list_reports(report_type, country_code, limit)


@router.get("/archive/accuracy/stats")
async def get_accuracy_stats():
    return await archive_service.get_accuracy()


@router.get("/archive/research")
async def list_research_reports(
    region_code: str | None = None,
    source_id: str | None = None,
    limit: int = Query(40, ge=1, le=200),
    auto_refresh: bool = True,
):
    if region_code and region_code not in research_archive_service.SUPPORTED_REGIONS:
        err = SP_6008("region_code")
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())

    try:
        return await research_archive_service.list_public_research_reports(
            region_code=region_code,
            source_id=source_id,
            limit=limit,
            auto_refresh=auto_refresh,
        )
    except Exception as exc:
        err = SP_5009(str(exc)[:240])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/archive/research/status")
async def get_research_archive_status(refresh_if_missing: bool = False):
    try:
        return await research_archive_service.get_public_research_status(
            refresh_if_missing=refresh_if_missing
        )
    except Exception as exc:
        err = SP_5009(str(exc)[:240])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/archive/research/refresh")
async def refresh_research_archive():
    try:
        return await research_archive_service.sync_public_research_reports(force=True)
    except Exception as exc:
        err = SP_5009(str(exc)[:240])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/archive/{report_id}")
async def get_archive(report_id: int):
    result = await archive_service.get_report(report_id)
    if not result:
        err = SP_6005(report_id)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())
    return result
