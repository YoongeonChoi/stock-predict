"""Bank of Korea ECOS API client for Korean economic indicators."""

import httpx
from app.data import cache
from app.config import get_settings

BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"

SERIES = {
    "base_rate": {"table": "722Y001", "item": "0101000"},
    "gdp_growth": {"table": "200Y002", "item": "10111"},
    "cpi_yoy": {"table": "901Y009", "item": "0"},
    "unemployment": {"table": "901Y027", "item": "3130000"},
    "export_growth": {"table": "403Y003", "item": "1"},
    "industrial_production": {"table": "901Y033", "item": "I11A"},
    "consumer_sentiment": {"table": "511Y002", "item": "FME"},
    "housing_price_index": {"table": "901Y062", "item": "P63AA"},
}


async def get_series(table_code: str, item_code: str, count: int = 12) -> list[dict]:
    settings = get_settings()
    if not settings.ecos_api_key:
        return []

    async def _fetch():
        url = (
            f"{BASE_URL}/{settings.ecos_api_key}/json/kr/1/{count}"
            f"/{table_code}/M/202301/209912/{item_code}"
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                body = resp.json()
                rows = body.get("StatisticSearch", {}).get("row", [])
                return [
                    {"date": r.get("TIME"), "value": _parse(r.get("DATA_VALUE"))}
                    for r in rows
                ]
        except Exception:
            return []

    return await cache.get_or_fetch(
        f"ecos:{table_code}:{item_code}", _fetch, settings.cache_ttl_economic
    )


async def get_kr_economic_snapshot() -> dict:
    data = {}
    for key, spec in SERIES.items():
        vals = await get_series(spec["table"], spec["item"], count=3)
        data[key] = vals[-1]["value"] if vals else None
    return data


def _parse(v) -> float | None:
    try:
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None
