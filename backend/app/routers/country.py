from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.country import COUNTRY_REGISTRY
from app.data import yfinance_client
from app.analysis.country_analyzer import analyze_country
from app.analysis.forecast_engine import forecast_index
from app.services import archive_service
from app.errors import SP_6001, SP_3001, SP_3004, SP_5002, SP_2005

router = APIRouter(prefix="/api", tags=["country"])


@router.get("/countries")
async def list_countries():
    results = []
    for code, info in COUNTRY_REGISTRY.items():
        indices_data = []
        for idx in info.indices:
            try:
                q = await yfinance_client.get_index_quote(idx.ticker)
            except Exception:
                SP_2005(idx.ticker).log()
                q = {"price": 0, "change_pct": 0}
            indices_data.append({
                "ticker": idx.ticker,
                "name": idx.name,
                "price": q.get("price", 0),
                "change_pct": q.get("change_pct", 0),
            })
        results.append({
            "code": code,
            "name": info.name,
            "name_local": info.name_local,
            "currency": info.currency,
            "indices": indices_data,
        })
    return results


@router.get("/country/{code}/report")
async def get_country_report(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report = await analyze_country(code)
    except Exception as e:
        err = SP_3001(code)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    try:
        await archive_service.save_report("country", report, country_code=code)
    except Exception as e:
        SP_5002(str(e)[:100]).log()

    return report


@router.get("/country/{code}/forecast")
async def get_country_forecast(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        primary = country.indices[0]
        forecast = await forecast_index(primary.ticker, primary.name, {}, "")
        return forecast
    except Exception as e:
        err = SP_3004(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/country/{code}/sectors")
async def list_sectors(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    from app.data.yfinance_client import UNIVERSE
    universe = UNIVERSE.get(code, {})
    sectors = []
    for s in country.sectors_gics:
        tickers = universe.get(s, [])
        sectors.append({
            "id": s.lower().replace(" ", "_"),
            "name": s,
            "country_code": code,
            "stock_count": len(tickers),
        })
    return sectors
