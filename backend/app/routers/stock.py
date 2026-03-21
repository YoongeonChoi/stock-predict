from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.analysis.stock_analyzer import analyze_stock
from app.data import yfinance_client
from app.services import archive_service
from app.errors import SP_3003, SP_6003, SP_2005, SP_5002

router = APIRouter(prefix="/api", tags=["stock"])


@router.get("/stock/{ticker}/detail")
async def get_stock_detail(ticker: str):
    try:
        detail = await analyze_stock(ticker)
    except Exception as e:
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    try:
        await archive_service.save_report("stock", detail, ticker=ticker)
    except Exception as e:
        SP_5002(str(e)[:100]).log()

    return detail


@router.get("/stock/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "3mo"):
    allowed = {"1mo", "3mo", "6mo", "1y", "2y"}
    if period not in allowed:
        err = SP_6003()
        err.log()
        return JSONResponse(status_code=400, content=err.to_dict())

    prices = await yfinance_client.get_price_history(ticker, period)
    if not prices:
        err = SP_2005(ticker)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    return {"ticker": ticker, "period": period, "data": prices}
