from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.errors import SP_5006
from app.services import system_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/diagnostics")
async def diagnostics():
    try:
        return await system_service.get_diagnostics()
    except Exception as exc:
        err = SP_5006(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
