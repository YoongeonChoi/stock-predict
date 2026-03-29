from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.errors import SP_5007
from app.services import research_service

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/predictions")
async def get_prediction_lab(
    limit_recent: int = Query(40, ge=10, le=100),
    refresh: bool = False,
):
    try:
        return await research_service.get_prediction_lab(limit_recent=limit_recent, refresh=refresh)
    except Exception as exc:
        err = SP_5007(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
