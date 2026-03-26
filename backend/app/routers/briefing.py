import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.errors import SP_5011, SP_5012, SP_5018
from app.services import briefing_service, market_session_service

router = APIRouter(prefix="/api", tags=["briefing"])
PUBLIC_ENDPOINT_TIMEOUT_SECONDS = 12


@router.get("/briefing/daily")
async def get_daily_briefing():
    try:
        return await asyncio.wait_for(
            briefing_service.get_daily_briefing(),
            timeout=PUBLIC_ENDPOINT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        err = SP_5018(f"Daily briefing exceeded {PUBLIC_ENDPOINT_TIMEOUT_SECONDS} seconds.")
        err.log("warning")
        return JSONResponse(status_code=504, content=err.to_dict())
    except Exception as exc:
        err = SP_5011(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/market/sessions")
async def get_market_sessions():
    try:
        return await market_session_service.get_market_sessions()
    except Exception as exc:
        err = SP_5012(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
