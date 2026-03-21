from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services import watchlist_service
from app.errors import SP_5003

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist")
async def get_watchlist():
    try:
        return await watchlist_service.get_watchlist()
    except Exception as e:
        err = SP_5003(f"list: {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/watchlist/{ticker}")
async def add_watchlist(ticker: str, country_code: str = "US"):
    try:
        await watchlist_service.add_to_watchlist(ticker, country_code)
        return {"status": "added", "ticker": ticker}
    except Exception as e:
        err = SP_5003(f"add({ticker}): {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str):
    try:
        await watchlist_service.remove_from_watchlist(ticker)
        return {"status": "removed", "ticker": ticker}
    except Exception as e:
        err = SP_5003(f"remove({ticker}): {e}")
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
