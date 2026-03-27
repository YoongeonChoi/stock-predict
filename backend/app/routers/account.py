from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.auth import AuthenticatedUser, get_current_user
from app.exceptions import ApiAppException
from app.errors import SP_5019
from app.models.account import AccountProfileUpdateRequest
from app.services import account_service

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account/me")
async def get_account_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await account_service.get_current_profile(current_user)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"profile: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.patch("/account/me")
async def patch_account_me(
    payload: AccountProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await account_service.update_current_profile(current_user, payload)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"profile update: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/account/username-availability")
async def get_username_availability(
    username: str = Query(default="", max_length=40),
):
    try:
        return await account_service.check_username_availability(username)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"username: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
