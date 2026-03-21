from fastapi import APIRouter, HTTPException
from app.analysis.stock_analyzer import analyze_stock
from app.data import yfinance_client
from app.services import archive_service

router = APIRouter(prefix="/api", tags=["stock"])


@router.get("/stock/{ticker}/detail")
async def get_stock_detail(ticker: str):
    try:
        detail = await analyze_stock(ticker)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed for {ticker}: {str(e)}")
    if "error" in detail:
        raise HTTPException(500, detail["error"])
    await archive_service.save_report("stock", detail, ticker=ticker)
    return detail


@router.get("/stock/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "3mo"):
    allowed = {"1mo", "3mo", "6mo", "1y", "2y"}
    if period not in allowed:
        raise HTTPException(400, f"Period must be one of {allowed}")
    prices = await yfinance_client.get_price_history(ticker, period)
    if not prices:
        raise HTTPException(404, f"No price data for {ticker}")
    return {"ticker": ticker, "period": period, "data": prices}
