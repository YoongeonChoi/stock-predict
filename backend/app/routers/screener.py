import logging
from fastapi import APIRouter, Query
from fastapi.params import Param
from app.data import yfinance_client, cache
from app.data.universe_data import get_universe
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited

router = APIRouter(prefix="/api", tags=["screener"])

ALLOWED_SORT_FIELDS = {
    "market_cap",
    "pe_ratio",
    "pb_ratio",
    "change_pct",
    "dividend_yield",
    "score",
    "current_price",
    "beta",
    "pct_from_52w_high",
    "revenue_growth",
    "roe",
    "avg_volume",
    "profit_margins",
}


def _normalize_query_param(value):
    if isinstance(value, Param):
        return value.default
    return value


@router.get("/screener")
async def screen_stocks(
    country: str = Query("KR", description="Country code: KR"),
    sector: str | None = Query(None, description="Sector filter"),
    market_cap_min: float | None = Query(None),
    market_cap_max: float | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    pe_min: float | None = Query(None),
    pe_max: float | None = Query(None),
    pb_max: float | None = Query(None),
    dividend_yield_min: float | None = Query(None),
    beta_max: float | None = Query(None),
    change_pct_min: float | None = Query(None),
    change_pct_max: float | None = Query(None),
    pct_from_52w_high_min: float | None = Query(None),
    pct_from_52w_high_max: float | None = Query(None),
    revenue_growth_min: float | None = Query(None),
    roe_min: float | None = Query(None),
    debt_to_equity_max: float | None = Query(None),
    avg_volume_min: float | None = Query(None),
    profitable_only: bool = Query(False),
    score_min: float | None = Query(None),
    sort_by: str = Query("market_cap", description="Sort field"),
    sort_dir: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200),
):
    """Screen stocks by various criteria."""
    country = _normalize_query_param(country)
    sector = _normalize_query_param(sector)
    market_cap_min = _normalize_query_param(market_cap_min)
    market_cap_max = _normalize_query_param(market_cap_max)
    price_min = _normalize_query_param(price_min)
    price_max = _normalize_query_param(price_max)
    pe_min = _normalize_query_param(pe_min)
    pe_max = _normalize_query_param(pe_max)
    pb_max = _normalize_query_param(pb_max)
    dividend_yield_min = _normalize_query_param(dividend_yield_min)
    beta_max = _normalize_query_param(beta_max)
    change_pct_min = _normalize_query_param(change_pct_min)
    change_pct_max = _normalize_query_param(change_pct_max)
    pct_from_52w_high_min = _normalize_query_param(pct_from_52w_high_min)
    pct_from_52w_high_max = _normalize_query_param(pct_from_52w_high_max)
    revenue_growth_min = _normalize_query_param(revenue_growth_min)
    roe_min = _normalize_query_param(roe_min)
    debt_to_equity_max = _normalize_query_param(debt_to_equity_max)
    avg_volume_min = _normalize_query_param(avg_volume_min)
    profitable_only = _normalize_query_param(profitable_only)
    score_min = _normalize_query_param(score_min)
    sort_by = _normalize_query_param(sort_by)
    sort_dir = _normalize_query_param(sort_dir)
    limit = _normalize_query_param(limit)
    country = country.upper()
    if country != "KR":
        country = "KR"
    cache_key = (
        f"screener:v5:{country}:{sector}:{market_cap_min}:{market_cap_max}:{price_min}:{price_max}:"
        f"{pe_min}:{pe_max}:{pb_max}:{dividend_yield_min}:{beta_max}:{change_pct_min}:{change_pct_max}:"
        f"{pct_from_52w_high_min}:{pct_from_52w_high_max}:{revenue_growth_min}:{roe_min}:{debt_to_equity_max}:"
        f"{avg_volume_min}:{profitable_only}:{score_min}:{sort_by}:{sort_dir}:{limit}"
    )
    
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
            pb = info.get("pb_ratio")
            dy = info.get("dividend_yield")
            beta = info.get("beta")
            avg_volume = float(info.get("avg_volume") or 0.0)
            roe = info.get("roe")
            revenue_growth = info.get("revenue_growth")
            debt_to_equity = info.get("debt_to_equity")
            profit_margins = info.get("profit_margins")

            if market_cap_min and mc < market_cap_min:
                return None
            if market_cap_max and mc > market_cap_max:
                return None
            if price_min and price < price_min:
                return None
            if price_max and price > price_max:
                return None
            if pe_min and (pe is None or pe < pe_min):
                return None
            if pe_max and (pe is None or pe > pe_max):
                return None
            if pb_max and (pb is None or pb > pb_max):
                return None
            if dividend_yield_min and (dy is None or dy < dividend_yield_min):
                return None
            if beta_max and (beta is None or beta > beta_max):
                return None

            prev = float(info.get("prev_close") or snapshot.get("prev_close") or price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            if change_pct_min is not None and change_pct < change_pct_min:
                return None
            if change_pct_max is not None and change_pct > change_pct_max:
                return None
            
            high_52w = info.get("52w_high") or price
            low_52w = info.get("52w_low") or price
            pct_from_52w_high = ((price - high_52w) / high_52w * 100) if high_52w else 0
            if pct_from_52w_high_min is not None and pct_from_52w_high < pct_from_52w_high_min:
                return None
            if pct_from_52w_high_max is not None and pct_from_52w_high > pct_from_52w_high_max:
                return None

            revenue_growth_pct = (float(revenue_growth) * 100.0) if revenue_growth is not None else None
            roe_pct = (float(roe) * 100.0) if roe is not None else None
            profit_margin_pct = (float(profit_margins) * 100.0) if profit_margins is not None else None
            if revenue_growth_min is not None and (revenue_growth_pct is None or revenue_growth_pct < revenue_growth_min):
                return None
            if roe_min is not None and (roe_pct is None or roe_pct < roe_min):
                return None
            if debt_to_equity_max is not None and (debt_to_equity is None or debt_to_equity > debt_to_equity_max):
                return None
            if avg_volume_min is not None and avg_volume < avg_volume_min:
                return None
            if profitable_only and (profit_margin_pct is None or profit_margin_pct <= 0):
                return None

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
                "pb_ratio": round(pb, 2) if pb else None,
                "dividend_yield": round(dy * 100, 2) if dy else None,
                "beta": round(beta, 2) if beta else None,
                "week52_high": high_52w,
                "week52_low": low_52w,
                "pct_from_52w_high": round(pct_from_52w_high, 2),
                "revenue_growth": round(revenue_growth_pct, 2) if revenue_growth_pct is not None else None,
                "roe": round(roe_pct, 2) if roe_pct is not None else None,
                "debt_to_equity": round(float(debt_to_equity), 2) if debt_to_equity is not None else None,
                "avg_volume": round(avg_volume, 2),
                "profit_margins": round(profit_margin_pct, 2) if profit_margin_pct is not None else None,
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
