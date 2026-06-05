from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.auth import AuthenticatedUser, get_current_user
from app.errors import SP_5021
from app.exceptions import ApiAppException
from app.models.investment_profile import InvestmentProfileResolveRequest, InvestmentProfileUpdateRequest
from app.services import investment_profile_service

router = APIRouter(prefix="/api", tags=["investment-profile"])


@router.get("/investment-profile")
async def get_investment_profile(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await investment_profile_service.get_investment_profile(current_user.id)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5021(f"profile get: {str(exc)[:200]}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.put("/investment-profile")
async def put_investment_profile(
    payload: InvestmentProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await investment_profile_service.update_investment_profile(current_user.id, payload)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5021(f"profile update: {str(exc)[:200]}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/investment-profile/options")
async def get_investment_profile_options(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return investment_profile_service.get_investment_profile_options()
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5021(f"profile options: {str(exc)[:200]}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/investment-profile/resolve")
async def post_investment_profile_resolve(
    payload: InvestmentProfileResolveRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return investment_profile_service.resolve_profile_from_questionnaire(payload)
    except ApiAppException:
        raise
    except Exception as exc:
        err = SP_5021(f"profile resolve: {str(exc)[:200]}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
