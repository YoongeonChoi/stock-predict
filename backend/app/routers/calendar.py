from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.errors import SP_6001, SP_6007
from app.services import calendar_service

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/calendar/{code}")
async def get_calendar(code: str, year: int | None = None, month: int | None = None):
    code = code.upper()
    if code not in ("US", "KR", "JP"):
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    if year is not None and not 2000 <= year <= 2100:
        err = SP_6007("year")
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())

    if month is not None and not 1 <= month <= 12:
        err = SP_6007("month")
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())

    return await calendar_service.get_calendar(code, year=year, month=month)

