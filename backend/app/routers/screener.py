import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.data import yfinance_client, cache
from app.data.universe_data import UNIVERSE, get_universe
from app.scoring.stock_scorer import score_stock

router = APIRouter(prefix="/api", tags=["screener"])


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
    cache_key = f"screener:{country}:{sector}:{market_cap_min}:{market_cap_max}:{pe_min}:{pe_max}:{dividend_yield_min}:{score_min}:{sort_by}:{sort_dir}:{limit}"
    
    cached = await cache.get(cache_key)
    if cached:
        return cached

    universe = await get_universe(country)
    tickers = []
    if sector:
        tickers = universe.get(sector, [])
    else:
        for sec_tickers in universe.values():
            tickers.extend(sec_tickers)

    results = []
    for ticker in tickers[:200]:
        try:
            info = await yfinance_client.get_stock_info(ticker)
            if not info.get("current_price"):
                continue

            mc = info.get("market_cap") or 0
            pe = info.get("pe_ratio")
            dy = info.get("dividend_yield")
            
            if market_cap_min and mc < market_cap_min:
                continue
            if market_cap_max and mc > market_cap_max:
                continue
            if pe_min and (pe is None or pe < pe_min):
                continue
            if pe_max and (pe is None or pe > pe_max):
                continue
            if dividend_yield_min and (dy is None or dy < dividend_yield_min):
                continue

            price = info.get("current_price", 0)
            prev = info.get("prev_close", price)
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
                        continue
                except Exception:
                    pass
            
            results.append({
                "ticker": ticker,
                "name": info.get("name", ticker),
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
            })
        except Exception as e:
            logging.warning("screener: failed %s: %s", ticker, e)
            continue

    reverse = sort_dir == "desc"
    sort_key = sort_by if sort_by in ("market_cap", "pe_ratio", "change_pct", "dividend_yield", "score", "current_price") else "market_cap"
    results.sort(key=lambda x: x.get(sort_key) or 0, reverse=reverse)
    results = results[:limit]

    sectors = list(universe.keys())

    response = {"results": results, "total": len(results), "sectors": sectors}
    await cache.set(cache_key, response, 600)
    return response
