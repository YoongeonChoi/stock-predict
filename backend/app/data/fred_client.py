"""FRED API client for US economic indicators."""

import httpx
from app.data import cache
from app.config import get_settings

BASE_URL = "https://api.stlouisfed.org/fred"

SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "gdp_growth": "A191RL1Q225SBEA",
    "cpi_yoy": "CPIAUCSL",
    "unemployment": "UNRATE",
    "capacity_utilization": "TCU",
    "treasury_10y": "GS10",
    "treasury_2y": "GS2",
    "sp500_pe": "MULTPL/SP500_PE_RATIO_MONTH",
    "vix": "VIXCLS",
    "credit_spread": "BAMLH0A0HYM2",
    "consumer_sentiment": "UMCSENT",
    "industrial_production": "INDPRO",
}


async def get_series(series_id: str, limit: int = 12) -> list[dict]:
    settings = get_settings()
    if not settings.fred_api_key:
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{BASE_URL}/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": settings.fred_api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": limit,
                    },
                )
                resp.raise_for_status()
                obs = resp.json().get("observations", [])
                return [
                    {"date": o["date"], "value": _parse_val(o["value"])}
                    for o in obs
                    if o["value"] != "."
                ]
        except Exception:
            return []

    return await cache.get_or_fetch(
        f"fred:{series_id}", _fetch, settings.cache_ttl_economic
    )


async def get_us_economic_snapshot() -> dict:
    """Fetch key US economic indicators for country scoring."""
    data = {}
    for key, sid in SERIES.items():
        if "/" in sid:
            continue
        vals = await get_series(sid, limit=3)
        data[key] = vals[0]["value"] if vals else None
    return data


async def get_treasury_spread() -> float | None:
    t10 = await get_series("GS10", limit=1)
    t2 = await get_series("GS2", limit=1)
    if t10 and t2 and t10[0]["value"] is not None and t2[0]["value"] is not None:
        return round(t10[0]["value"] - t2[0]["value"], 3)
    return None


def _parse_val(v: str) -> float | None:
    try:
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None
