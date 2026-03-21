from fastapi import APIRouter, HTTPException
from app.services import calendar_service

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/calendar/{code}")
async def get_calendar(code: str):
    code = code.upper()
    if code not in ("US", "KR", "JP"):
        raise HTTPException(404, f"Country {code} not supported")
    return await calendar_service.get_calendar(code)
