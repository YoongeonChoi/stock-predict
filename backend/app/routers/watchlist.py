from fastapi import APIRouter
from app.services import watchlist_service

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist")
async def get_watchlist():
    return await watchlist_service.get_watchlist()


@router.post("/watchlist/{ticker}")
async def add_watchlist(ticker: str, country_code: str = "US"):
    await watchlist_service.add_to_watchlist(ticker, country_code)
    return {"status": "added", "ticker": ticker}


@router.delete("/watchlist/{ticker}")
async def remove_watchlist(ticker: str):
    await watchlist_service.remove_from_watchlist(ticker)
    return {"status": "removed", "ticker": ticker}
