"""Financial Modeling Prep Basic tier client (250 calls/day)."""

import logging

import httpx

from app.config import get_settings
from app.data import cache
from app.errors import SP_1005, SP_2006

BASE = "https://financialmodelingprep.com/api/v3"
SCREENING_DISABLED_TTL = 21600

log = logging.getLogger("stock_predict.fmp")


def _screening_disabled_key(exchange: str) -> str:
    return f"fmp_screen_disabled:{exchange.upper()}"


def _feature_disabled_key(feature: str) -> str:
    return f"fmp_feature_disabled:{feature}"


async def _mark_screening_unavailable(exchange: str, status_code: int, detail: str) -> None:
    key = _screening_disabled_key(exchange)
    existing = await cache.get(key)
    if existing:
        return
    payload = {"status_code": status_code, "detail": detail}
    await cache.set(key, payload, SCREENING_DISABLED_TTL)
    hours = max(1, SCREENING_DISABLED_TTL // 3600)
    log.warning(
        "FMP stock screener for %s disabled for %sh after HTTP %s. Falling back to curated universe.",
        exchange.upper(),
        hours,
        status_code,
    )


async def get_screening_status(exchange: str) -> dict | None:
    return await cache.get(_screening_disabled_key(exchange))


async def _mark_feature_unavailable(feature: str, status_code: int, detail: str) -> None:
    key = _feature_disabled_key(feature)
    existing = await cache.get(key)
    if existing:
        return
    payload = {"status_code": status_code, "detail": detail}
    await cache.set(key, payload, SCREENING_DISABLED_TTL)
    hours = max(1, SCREENING_DISABLED_TTL // 3600)
    log.warning(
        "FMP %s disabled for %sh after HTTP %s. Falling back without FMP enrichment.",
        feature,
        hours,
        status_code,
    )


async def _feature_available(feature: str) -> bool:
    return await cache.get(_feature_disabled_key(feature)) is None


async def get_feature_status(feature: str) -> dict | None:
    return await cache.get(_feature_disabled_key(feature))


async def probe_stock_screener(exchange: str, market_cap_min: int = 1_000_000_000) -> bool:
    settings = get_settings()
    if not settings.fmp_api_key:
        return False

    if await get_screening_status(exchange):
        return False

    probe_key = f"fmp_screen_probe:{exchange}:{market_cap_min}"

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE}/stock-screener",
                    params={
                        "exchange": exchange,
                        "marketCapMoreThan": market_cap_min,
                        "limit": 1,
                        "apikey": settings.fmp_api_key,
                    },
                )
                resp.raise_for_status()
                return {"ok": True}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                detail = f"probe({exchange}): {exc}"
                await _mark_screening_unavailable(exchange, exc.response.status_code, detail)
                return {"ok": False, "detail": detail}
            SP_2006(f"screen_probe({exchange}): {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"screen_probe({exchange}): {exc}").log("warning")
        return {"ok": False}

    result = await cache.get_or_fetch(probe_key, _fetch, 900)
    return bool(result and result.get("ok"))


async def get_stock_peers(ticker: str) -> list[str]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
        return []
    if not await _feature_available("stock_peers"):
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                await _mark_feature_unavailable("stock_peers", exc.response.status_code, f"peers({ticker}): {exc}")
                return []
            SP_2006(f"peers({ticker}): {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"peers({ticker}): {exc}").log("warning")
        return []

    return await cache.get_or_fetch(
        f"fmp_peers:{ticker}", _fetch, settings.cache_ttl_fmp
    )


async def get_earning_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
        return []
    if not await _feature_available("earning_calendar"):
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(
                    f"{BASE}/earning_calendar",
                    params={"from": from_date, "to": to_date, "apikey": settings.fmp_api_key},
                )
                resp.raise_for_status()
                return resp.json()[:100]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                await _mark_feature_unavailable("earning_calendar", exc.response.status_code, f"earning_calendar: {exc}")
                return []
            SP_2006(f"earning_calendar: {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"earning_calendar: {exc}").log("warning")
            return []

    return await cache.get_or_fetch(
        f"fmp_earn_cal:v2:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
    )


async def get_economic_calendar(from_date: str, to_date: str) -> list[dict]:
    settings = get_settings()
    if not settings.fmp_api_key:
        SP_1005().log("debug")
        return []
    if not await _feature_available("economic_calendar"):
        return []

    async def _fetch():
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get(
                    f"{BASE}/economic_calendar",
                    params={"from": from_date, "to": to_date, "apikey": settings.fmp_api_key},
                )
                resp.raise_for_status()
                return resp.json()[:200]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                await _mark_feature_unavailable("economic_calendar", exc.response.status_code, f"economic_calendar: {exc}")
                return []
            SP_2006(f"economic_calendar: {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"economic_calendar: {exc}").log("warning")
            return []

    return await cache.get_or_fetch(
        f"fmp_econ_cal:v2:{from_date}:{to_date}", _fetch, settings.cache_ttl_fmp
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
    if await get_screening_status(exchange):
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                detail = f"screen({exchange},{sector}): {exc}"
                await _mark_screening_unavailable(exchange, exc.response.status_code, detail)
                return []
            SP_2006(f"screen({exchange},{sector}): {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"screen({exchange},{sector}): {exc}").log("warning")
        return []

    return await cache.get_or_fetch(params_key, _fetch, 86400)


async def get_dcf(ticker: str) -> float | None:
    settings = get_settings()
    if not settings.fmp_api_key:
        return None
    if not await _feature_available("dcf"):
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403, 429}:
                await _mark_feature_unavailable("dcf", exc.response.status_code, f"dcf({ticker}): {exc}")
                return None
            SP_2006(f"dcf({ticker}): {exc}").log("warning")
        except Exception as exc:
            SP_2006(f"dcf({ticker}): {exc}").log("warning")
        return None

    return await cache.get_or_fetch(f"fmp_dcf:{ticker}", _fetch, settings.cache_ttl_fmp)
