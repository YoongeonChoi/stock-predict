from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.auth import AuthenticatedUser, get_current_user
from app.services import watchlist_service
from app.errors import SP_5003

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist")
async def get_watchlist(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await watchlist_service.get_watchlist(current_user.id)
    except Exception as e:
        err = SP_5003(f"list: {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/watchlist/{ticker}")
async def add_watchlist(
    ticker: str,
    country_code: str = "KR",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        resolution = await watchlist_service.add_to_watchlist(current_user.id, ticker, country_code)
        return {"status": "added", "ticker": resolution["ticker"], "country_code": resolution["country_code"], "note": resolution["note"]}
    except Exception as e:
        err = SP_5003(f"add({ticker}): {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        await watchlist_service.remove_from_watchlist(current_user.id, ticker)
        return {"status": "removed", "ticker": ticker}
    except Exception as e:
        err = SP_5003(f"remove({ticker}): {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
