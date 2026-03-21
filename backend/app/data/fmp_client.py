"""Financial Modeling Prep Basic tier client (250 calls/day)."""

import httpx
from app.data import cache
from app.config import get_settings
from app.errors import SP_1005, SP_2006

BASE = "https://financialmodelingprep.com/api/v3"


async def get_stock_peers(ticker: str) -> list[str]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
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
        except Exception as e:
            SP_2006(f"peers({ticker}): {e}").log()
        return []

    return await cache.get_or_fetch(
        f"fmp_peers:{ticker}", _fetch, settings.cache_ttl_fmp
    )


async def get_earning_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
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
        except Exception as e:
            SP_2006(f"earning_calendar: {e}").log()
            return []

    return await cache.get_or_fetch(
        f"fmp_earn_cal:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
    )


async def get_economic_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
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
        except Exception as e:
            SP_2006(f"economic_calendar: {e}").log()
            return []

    return await cache.get_or_fetch(
        f"fmp_econ_cal:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
    )


async def screen_stocks(
    exchange: str,
    sector: str | None = None,
    market_cap_min: int = 1_000_000_000,
    limit: int = 50,
) -> list[str]:
    """Fetch top stocks by market cap from FMP Stock Screener.

    Args:
        exchange: NYSE, NASDAQ, KSE (Korea), TSE (Japan), etc.
        sector: GICS sector name (optional filter)
        market_cap_min: Minimum market cap in USD
        limit: Max number of results
    Returns:
        List of ticker symbols
    """
    settings = get_settings()
    if not settings.fmp_api_key:
        return []

    params_key = f"fmp_screen:{exchange}:{sector}:{market_cap_min}:{limit}"

    async def _fetch():
        try:
            params = {
                "exchange": exchange,
                "marketCapMoreThan": market_cap_min,
                "limit": limit,
                "apikey": settings.fmp_api_key,
            }
            if sector:
                params["sector"] = sector
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{BASE}/stock-screener", params=params)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return [item["symbol"] for item in data if "symbol" in item]
        except Exception as e:
            SP_2006(f"screen({exchange},{sector}): {e}").log()
        return []

    return await cache.get_or_fetch(params_key, _fetch, 86400)


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
        except Exception as e:
            SP_2006(f"dcf({ticker}): {e}").log()
        return None

    return await cache.get_or_fetch(f"fmp_dcf:{ticker}", _fetch, settings.cache_ttl_fmp)
