from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.errors import SP_5008, SP_5013, SP_5015, SP_5016, SP_5017, SP_6009, SP_6013
from app.services import ideal_portfolio_service, portfolio_service, portfolio_event_service, portfolio_recommendation_service

router = APIRouter(prefix="/api", tags=["portfolio"])


class HoldingCreate(BaseModel):
    ticker: str
    buy_price: float
    quantity: float
    buy_date: str
    country_code: str = "US"


class PortfolioProfileUpdate(BaseModel):
    total_assets: float = 0
    cash_balance: float = 0
    monthly_budget: float = 0


@router.get("/portfolio")
async def get_portfolio():
    try:
        data = await portfolio_service.get_portfolio()
        return data
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/profile")
async def get_portfolio_profile():
    try:
        return await portfolio_service.get_portfolio_profile()
    except Exception as e:
        err = SP_5017(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.put("/portfolio/profile")
async def update_portfolio_profile(body: PortfolioProfileUpdate):
    try:
        return await portfolio_service.update_portfolio_profile(
            body.total_assets,
            body.cash_balance,
            body.monthly_budget,
        )
    except ValueError as e:
        err = SP_6013(str(e)[:200])
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())
    except Exception as e:
        err = SP_5017(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/ideal")
async def get_ideal_portfolio(refresh: bool = False, history_limit: int = 10):
    try:
        data = await ideal_portfolio_service.get_daily_ideal_portfolio(
            force_refresh=refresh,
            history_limit=max(3, min(history_limit, 30)),
        )
        return data
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/event-radar")
async def get_portfolio_event_radar(days: int = 14):
    try:
        return await portfolio_event_service.get_portfolio_event_radar(days)
    except Exception as e:
        err = SP_5013(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/recommendations/conditional")
async def get_conditional_portfolio_recommendations(
    country_code: str = "ALL",
    sector: str = "ALL",
    style: str = "balanced",
    max_items: int = 5,
    min_up_probability: float = 54.0,
    exclude_holdings: bool = True,
    watchlist_only: bool = False,
):
    try:
        return await portfolio_recommendation_service.get_conditional_recommendations(
            country_code=country_code,
            sector=sector,
            style=style,
            max_items=max_items,
            min_up_probability=min_up_probability,
            exclude_holdings=exclude_holdings,
            watchlist_only=watchlist_only,
        )
    except Exception as e:
        err = SP_5015(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/recommendations/optimal")
async def get_optimal_portfolio_recommendation():
    try:
        return await portfolio_recommendation_service.get_optimal_recommendation()
    except Exception as e:
        err = SP_5016(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/portfolio/holdings")
async def add_holding(body: HoldingCreate):
    try:
        saved = await portfolio_service.add_holding(
            body.ticker, body.buy_price, body.quantity, body.buy_date, body.country_code
        )
        return {"status": "ok", **saved}
    except ValueError as e:
        err = SP_6009(str(e)[:200])
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.put("/portfolio/holdings/{holding_id}")
async def update_holding(holding_id: int, body: HoldingCreate):
    try:
        saved = await portfolio_service.update_holding(
            holding_id,
            body.ticker,
            body.buy_price,
            body.quantity,
            body.buy_date,
            body.country_code,
        )
        return {"status": "ok", **saved}
    except ValueError as e:
        err = SP_6009(str(e)[:200])
        err.log("warning")
        return JSONResponse(status_code=400, content=err.to_dict())
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
