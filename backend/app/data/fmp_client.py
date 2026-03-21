"""Financial Modeling Prep Basic tier client (250 calls/day)."""

import httpx
from app.data import cache
from app.config import get_settings

BASE = "https://financialmodelingprep.com/api/v3"


async def get_stock_peers(ticker: str) -> list[str]:
    settings = get_settings()
    if not settings.fmp_api_key:
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/stock_peers", params={"symbol": ticker, "apikey": settings.fmp_api_key}
                )
                resp.raise_for_status()
                data = resp.json()
                if data and isinstance(data, list):
                    return data[0].get("peersList", [])[:10]
        except Exception:
            pass
        return []

    return await cache.get_or_fetch(
        f"fmp_peers:{ticker}", _fetch, settings.cache_ttl_fmp
    )


async def get_earning_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/earning_calendar",
                    params={"from": from_date, "to": to_date, "apikey": settings.fmp_api_key},
                )
                resp.raise_for_status()
                return resp.json()[:100]
        except Exception:
            return []

    return await cache.get_or_fetch(
        f"fmp_earn_cal:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
    )


async def get_economic_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/economic_calendar",
                    params={"from": from_date, "to": to_date, "apikey": settings.fmp_api_key},
                )
                resp.raise_for_status()
                return resp.json()[:200]
        except Exception:
            return []

    return await cache.get_or_fetch(
        f"fmp_econ_cal:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
    )


async def get_dcf(ticker: str) -> float | None:
    settings = get_settings()
    if not settings.fmp_api_key:
        return None

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/discounted-cash-flow/{ticker}",
                    params={"apikey": settings.fmp_api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                if data and isinstance(data, list):
                    return data[0].get("dcf")
        except Exception:
            pass
        return None

    return await cache.get_or_fetch(f"fmp_dcf:{ticker}", _fetch, settings.cache_ttl_fmp)
