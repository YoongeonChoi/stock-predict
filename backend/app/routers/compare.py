from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services import compare_service
from app.errors import SP_6004

router = APIRouter(prefix="/api", tags=["compare"])


@router.get("/compare")
async def compare_stocks(tickers: str = Query(..., description="Comma-separated tickers")):
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        err = SP_6004()
        err.log()
        return JSONResponse(status_code=400, content=err.to_dict())
    if len(ticker_list) > 4:
        ticker_list = ticker_list[:4]
    return await compare_service.compare_stocks(ticker_list)
