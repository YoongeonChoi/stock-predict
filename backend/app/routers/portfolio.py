import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.auth import AuthenticatedUser, get_current_user
from app.errors import SP_5008, SP_5013, SP_5015, SP_5016, SP_5017, SP_6009, SP_6013
from app.services import ideal_portfolio_service, portfolio_event_service, portfolio_recommendation_service, portfolio_service, route_stability_service
from app.utils import build_route_trace

router = APIRouter(prefix="/api", tags=["portfolio"])


class HoldingCreate(BaseModel):
    ticker: str
    buy_price: float
    quantity: float
    buy_date: str
    country_code: str = "KR"


class PortfolioProfileUpdate(BaseModel):
    total_assets: float = 0
    cash_balance: float = 0
    monthly_budget: float = 0


@router.get("/portfolio")
async def get_portfolio(current_user: AuthenticatedUser = Depends(get_current_user)):
    started_at = time.perf_counter()
    try:
        data = await portfolio_service.get_portfolio(current_user.id)
        route_stability_service.record_route_trace(
            "portfolio_workspace",
            build_route_trace(
                route_key="portfolio_workspace",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                upstream_source="portfolio_service",
                payload=data,
            ),
        )
        return data
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        route_stability_service.record_route_trace(
            "portfolio_workspace",
            build_route_trace(
                route_key="portfolio_workspace",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                upstream_source="portfolio_service",
                fallback_reason="portfolio_workspace_error",
                served_state="degraded",
            ),
        )
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/profile")
async def get_portfolio_profile(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await portfolio_service.get_portfolio_profile(current_user.id)
    except Exception as e:
        err = SP_5017(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.put("/portfolio/profile")
async def update_portfolio_profile(
    body: PortfolioProfileUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await portfolio_service.update_portfolio_profile(
            current_user.id,
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
async def get_portfolio_event_radar(days: int = 14, current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await portfolio_event_service.get_portfolio_event_radar(current_user.id, days)
    except Exception as e:
        err = SP_5013(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/portfolio/recommendations/conditional")
async def get_conditional_portfolio_recommendations(
    country_code: str = "KR",
    sector: str = "ALL",
    style: str = "balanced",
    max_items: int = 5,
    min_up_probability: float = 54.0,
    exclude_holdings: bool = True,
    watchlist_only: bool = False,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await portfolio_recommendation_service.get_conditional_recommendations(
            user_id=current_user.id,
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
async def get_optimal_portfolio_recommendation(current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        return await portfolio_recommendation_service.get_optimal_recommendation(current_user.id)
    except Exception as e:
        err = SP_5016(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.post("/portfolio/holdings")
async def add_holding(body: HoldingCreate, current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        saved = await portfolio_service.add_holding(
            current_user.id,
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


@router.put("/portfolio/holdings/{holding_id}")
async def update_holding(
    holding_id: int,
    body: HoldingCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        saved = await portfolio_service.update_holding(
            current_user.id,
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
async def delete_holding(holding_id: int, current_user: AuthenticatedUser = Depends(get_current_user)):
    try:
        await portfolio_service.remove_holding(current_user.id, holding_id)
        return {"status": "ok"}
    except Exception as e:
        err = SP_5008(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
