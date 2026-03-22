from fastapi import APIRouter, Query

from app.services import research_service

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/predictions")
async def get_prediction_lab(
    limit_recent: int = Query(40, ge=10, le=100),
    refresh: bool = True,
):
    return await research_service.get_prediction_lab(limit_recent=limit_recent, refresh=refresh)
