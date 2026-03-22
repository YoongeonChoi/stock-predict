from fastapi import APIRouter

from app.services import system_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/diagnostics")
async def diagnostics():
    return await system_service.get_diagnostics()
