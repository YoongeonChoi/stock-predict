from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.errors import SP_5008
from app.services import portfolio_service

router = APIRouter(prefix="/api", tags=["portfolio"])


class HoldingCreate(BaseModel):
    ticker: str
    buy_price: float
    quantity: float
    buy_date: str
    country_code: str = "US"


@router.get("/portfolio")
async def get_portfolio():
    try:
        data = await portfolio_service.get_portfolio()
        return data
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/portfolio/holdings")
async def add_holding(body: HoldingCreate):
    try:
        await portfolio_service.add_holding(
            body.ticker, body.buy_price, body.quantity, body.buy_date, body.country_code
        )
        return {"status": "ok"}
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.delete("/portfolio/holdings/{holding_id}")
async def delete_holding(holding_id: int):
    try:
        await portfolio_service.remove_holding(holding_id)
        return {"status": "ok"}
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
