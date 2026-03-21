from fastapi import APIRouter, HTTPException
from app.models.country import COUNTRY_REGISTRY
from app.analysis.sector_analyzer import analyze_sector
from app.services import archive_service

router = APIRouter(prefix="/api", tags=["sector"])

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


@router.get("/country/{code}/sector/{sector_id}/report")
async def get_sector_report(code: str, sector_id: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        raise HTTPException(404, f"Country {code} not supported")

    sector_name = SECTOR_MAP.get(sector_id)
    if not sector_name:
        raise HTTPException(404, f"Sector {sector_id} not found")

    report = await analyze_sector(code, sector_name)
    if "error" in report:
        raise HTTPException(500, report["error"])

    await archive_service.save_report("sector", report, country_code=code, sector_id=sector_id)
    return report
