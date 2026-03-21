"""Bank of Japan data client for Japanese economic indicators.

BOJ Time-Series Data uses a REST API with CSV/JSON output.
"""

import httpx
from app.data import cache
from app.config import get_settings

BASE_URL = "https://www.stat-search.boj.or.jp/ssi/mtsui/rest/getBojTimeSeriesData"

SERIES = {
    "policy_rate": "IR01'MADR1Z@D",
    "cpi_yoy": "PR01'YCMA@M",
    "industrial_production": "CI02'0001@M",
    "unemployment": "LF02'LF2MAHP@M",
    "tankan_large_mfg": "DI01'DTK1D11@Q",
}


async def get_series(series_code: str, limit: int = 12) -> list[dict]:
    """Fetch a BOJ time series. Falls back to empty on failure."""

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    BASE_URL,
                    params={"code": series_code, "format": "json", "lang": "en"},
                )
                if resp.status_code != 200:
                    return []
                body = resp.json()
                obs = body.get("data", [])[-limit:]
                return [
                    {"date": o.get("date", ""), "value": _parse(o.get("value"))}
                    for o in obs
                ]
        except Exception:
            return []

    settings = get_settings()
    return await cache.get_or_fetch(
        f"boj:{series_code}", _fetch, settings.cache_ttl_economic
    )


async def get_jp_economic_snapshot() -> dict:
    data = {}
    for key, code in SERIES.items():
        vals = await get_series(code, limit=3)
        data[key] = vals[-1]["value"] if vals else None
    return data


def _parse(v) -> float | None:
    try:
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None
