from fastapi import APIRouter, Query
from app.services import compare_service

router = APIRouter(prefix="/api", tags=["compare"])


@router.get("/compare")
async def compare_stocks(tickers: str = Query(..., description="Comma-separated tickers")):
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        return {"error": "Provide at least 2 tickers"}
    if len(ticker_list) > 4:
        ticker_list = ticker_list[:4]
    return await compare_service.compare_stocks(ticker_list)
