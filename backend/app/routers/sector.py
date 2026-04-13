from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.country import COUNTRY_REGISTRY
from app.errors import SP_6001, SP_6002, SP_3002, SP_5002
from app.utils.lazy_module import LazyModuleProxy

router = APIRouter(prefix="/api", tags=["sector"])
archive_service = LazyModuleProxy("app.services.archive_service")

SECTOR_MAP = {
    "energy": "Energy",
    "materials": "Materials",
    "industrials": "Industrials",
    "consumer_discretionary": "Consumer Discretionary",
    "consumer_staples": "Consumer Staples",
    "health_care": "Health Care",
    "financials": "Financials",
    "information_technology": "Information Technology",
    "communication_services": "Communication Services",
    "utilities": "Utilities",
    "real_estate": "Real Estate",
}


async def analyze_sector(*args, **kwargs):
    from app.analysis.sector_analyzer import analyze_sector as _analyze_sector

    return await _analyze_sector(*args, **kwargs)


@router.get("/country/{code}/sector/{sector_id}/report")
async def get_sector_report(code: str, sector_id: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    sector_name = SECTOR_MAP.get(sector_id)
    if not sector_name:
        err = SP_6002(sector_id)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report = await analyze_sector(code, sector_name)
    except Exception as e:
        err = SP_3002(sector_name)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    try:
        await archive_service.save_report("sector", report, country_code=code, sector_id=sector_id)
    except Exception as e:
        SP_5002(str(e)[:100]).log()

    return report
