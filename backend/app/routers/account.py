from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.auth import AuthenticatedUser, get_current_user
from app.exceptions import ApiAppException
from app.errors import SP_5019
from app.models.account import AccountDeleteRequest, AccountProfileUpdateRequest, SignUpValidationRequest
from app.services import account_service, public_rate_limit_service

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


@router.delete("/account/me")
async def delete_account_me(
    payload: AccountDeleteRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await account_service.delete_current_account(current_user, payload)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"profile delete: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/account/signup/validate")
async def post_signup_validation(
    request: Request,
    payload: SignUpValidationRequest,
):
    try:
        public_rate_limit_service.enforce_public_account_rate_limit(request, "signup_validate")
        return await account_service.validate_signup(payload)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"signup validate: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/account/username-availability")
async def get_username_availability(
    request: Request,
    username: str = Query(default="", max_length=40),
):
    try:
        public_rate_limit_service.enforce_public_account_rate_limit(request, "username_availability")
        return await account_service.check_username_availability(username)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5019(f"username: {exc}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
