from fastapi import APIRouter, HTTPException
from app.models.country import COUNTRY_REGISTRY
from app.data import yfinance_client
from app.analysis.country_analyzer import analyze_country
from app.analysis.forecast_engine import forecast_index
from app.services import archive_service

router = APIRouter(prefix="/api", tags=["country"])


@router.get("/countries")
async def list_countries():
    results = []
    for code, info in COUNTRY_REGISTRY.items():
        indices_data = []
        for idx in info.indices:
            q = await yfinance_client.get_index_quote(idx.ticker)
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
        raise HTTPException(404, f"Country {code} not supported")
    report = await analyze_country(code)
    if "error" in report:
        raise HTTPException(500, report["error"])
    await archive_service.save_report("country", report, country_code=code)
    return report


@router.get("/country/{code}/forecast")
async def get_country_forecast(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        raise HTTPException(404, f"Country {code} not supported")
    primary = country.indices[0]
    forecast = await forecast_index(
        primary.ticker, primary.name, {}, ""
    )
    return forecast


@router.get("/country/{code}/sectors")
async def list_sectors(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        raise HTTPException(404, f"Country {code} not supported")
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
