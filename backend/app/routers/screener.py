import logging
from fastapi import APIRouter, Query
from app.data import yfinance_client, cache
from app.data.universe_data import get_universe
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited

router = APIRouter(prefix="/api", tags=["screener"])

ALLOWED_SORT_FIELDS = {"market_cap", "pe_ratio", "change_pct", "dividend_yield", "score", "current_price"}


@router.get("/screener")
async def screen_stocks(
    country: str = Query("US", description="Country code: US, KR, JP"),
    sector: str | None = Query(None, description="Sector filter"),
    market_cap_min: float | None = Query(None),
    market_cap_max: float | None = Query(None),
    pe_min: float | None = Query(None),
    pe_max: float | None = Query(None),
    dividend_yield_min: float | None = Query(None),
    score_min: float | None = Query(None),
    sort_by: str = Query("market_cap", description="Sort field"),
    sort_dir: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200),
):
    """Screen stocks by various criteria."""
    country = country.upper()
    cache_key = f"screener:v2:{country}:{sector}:{market_cap_min}:{market_cap_max}:{pe_min}:{pe_max}:{dividend_yield_min}:{score_min}:{sort_by}:{sort_dir}:{limit}"
    
    cached = await cache.get(cache_key)
    if cached:
        return cached

    universe = await get_universe(country)
    tickers = []
    seen = set()
    if sector:
        for ticker in universe.get(sector, []):
            if ticker in seen:
                continue
            seen.add(ticker)
            tickers.append(ticker)
    else:
        for sec_tickers in universe.values():
            for ticker in sec_tickers:
                if ticker in seen:
                    continue
                seen.add(ticker)
                tickers.append(ticker)

    async def _screen_ticker(ticker: str):
        try:
            snapshot = await yfinance_client.get_market_snapshot(ticker, period="6mo")
            if not snapshot.get("valid"):
                return None

            info = await yfinance_client.get_stock_info(ticker)
            price = float(info.get("current_price") or snapshot.get("current_price") or 0.0)
            if price <= 0:
                return None

            mc = float(info.get("market_cap") or snapshot.get("market_cap") or 0.0)
            pe = info.get("pe_ratio")
            dy = info.get("dividend_yield")
            
            if market_cap_min and mc < market_cap_min:
                return None
            if market_cap_max and mc > market_cap_max:
                return None
            if pe_min and (pe is None or pe < pe_min):
                return None
            if pe_max and (pe is None or pe > pe_max):
                return None
            if dividend_yield_min and (dy is None or dy < dividend_yield_min):
                return None

            prev = float(info.get("prev_close") or snapshot.get("prev_close") or price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            
            high_52w = info.get("52w_high") or price
            low_52w = info.get("52w_low") or price
            pct_from_52w_high = ((price - high_52w) / high_52w * 100) if high_52w else 0

            score_total = None
            if score_min is not None:
                try:
                    prices = await yfinance_client.get_price_history(ticker, period="3mo")
                    qs = score_stock(info, price_hist=prices)
                    score_total = round(qs.total, 1)
                    if score_total < score_min:
                        return None
                except Exception:
                    pass

            return {
                "ticker": ticker,
                "name": info.get("name") or snapshot.get("name") or ticker,
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "market_cap": mc,
                "current_price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "pe_ratio": round(pe, 2) if pe else None,
                "pb_ratio": round(info.get("pb_ratio", 0), 2) if info.get("pb_ratio") else None,
                "dividend_yield": round(dy * 100, 2) if dy else None,
                "beta": round(info.get("beta", 0), 2) if info.get("beta") else None,
                "week52_high": high_52w,
                "week52_low": low_52w,
                "pct_from_52w_high": round(pct_from_52w_high, 2),
                "score": score_total,
                "country_code": country,
            }
        except Exception as e:
            logging.warning("screener: failed %s: %s", ticker, e)
            return None

    screened = await gather_limited(tickers[:200], _screen_ticker, limit=6)
    results = [item for item in screened if not isinstance(item, Exception) and item is not None]

    reverse = sort_dir == "desc"
    sort_key = sort_by if sort_by in ALLOWED_SORT_FIELDS else "market_cap"
    results.sort(key=lambda x: x.get(sort_key) or 0, reverse=reverse)
    results = results[:limit]

    sectors = list(universe.keys())

    response = {"results": results, "total": len(results), "sectors": sectors}
    await cache.set(cache_key, response, 600)
    return response
