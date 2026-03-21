from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services import calendar_service
from app.errors import SP_6001

router = APIRouter(prefix="/api", tags=["calendar"])


@router.get("/calendar/{code}")
async def get_calendar(code: str):
    code = code.upper()
    if code not in ("US", "KR", "JP"):
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())
    return await calendar_service.get_calendar(code)
