from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services import archive_service
from app.errors import SP_6005

router = APIRouter(prefix="/api", tags=["archive"])


@router.get("/archive")
async def list_archives(
    report_type: str | None = None,
    country_code: str | None = None,
    limit: int = Query(50, le=200),
):
    return await archive_service.list_reports(report_type, country_code, limit)


@router.get("/archive/{report_id}")
async def get_archive(report_id: int):
    result = await archive_service.get_report(report_id)
    if not result:
        err = SP_6005(report_id)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())
    return result


@router.get("/archive/accuracy/stats")
async def get_accuracy_stats():
    return await archive_service.get_accuracy()
