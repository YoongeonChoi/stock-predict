import asyncio
import logging
from fastapi import APIRouter, Query
from fastapi.params import Param
from app.config import get_settings
from app.data import cache, kr_market_quote_client, yfinance_client
from app.data.universe_data import get_universe
from app.errors import SP_5018
from app.runtime import get_or_create_background_job
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited
from app.utils.memory_hygiene import maybe_trim_process_memory

router = APIRouter(prefix="/api", tags=["screener"])
settings = get_settings()
PUBLIC_SCREENER_TIMEOUT_SECONDS = 10
SCREENER_RESPONSE_CACHE_TTL = 600
SCREENER_MAX_CANDIDATES = 36
SCREENER_MAX_SECTOR_CANDIDATES = 16
SCREENER_MAX_PER_SECTOR = 4
SCREENER_CONCURRENCY = 4
SCREENER_ENRICHMENT_BUDGET = 12
SCREENER_COLD_START_KR_CANDIDATES = 10

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


def _build_screener_cache_key(
    *,
    country: str,
    sector: str | None,
    market_cap_min: float | None,
    market_cap_max: float | None,
    price_min: float | None,
    price_max: float | None,
    pe_min: float | None,
    pe_max: float | None,
    pb_max: float | None,
    dividend_yield_min: float | None,
    beta_max: float | None,
    change_pct_min: float | None,
    change_pct_max: float | None,
    pct_from_52w_high_min: float | None,
    pct_from_52w_high_max: float | None,
    revenue_growth_min: float | None,
    roe_min: float | None,
    debt_to_equity_max: float | None,
    avg_volume_min: float | None,
    profitable_only: bool,
    score_min: float | None,
    sort_by: str,
    sort_dir: str,
    limit: int,
) -> str:
    return (
        f"screener:v7:{country}:{sector}:{market_cap_min}:{market_cap_max}:{price_min}:{price_max}:"
        f"{pe_min}:{pe_max}:{pb_max}:{dividend_yield_min}:{beta_max}:{change_pct_min}:{change_pct_max}:"
        f"{pct_from_52w_high_min}:{pct_from_52w_high_max}:{revenue_growth_min}:{roe_min}:{debt_to_equity_max}:"
        f"{avg_volume_min}:{profitable_only}:{score_min}:{sort_by}:{sort_dir}:{limit}"
    )


def _select_candidate_tickers(universe: dict[str, list[str]], sector: str | None) -> list[str]:
    seen: set[str] = set()
    tickers: list[str] = []

    if sector:
        for ticker in universe.get(sector, [])[:SCREENER_MAX_SECTOR_CANDIDATES]:
            if ticker in seen:
                continue
            seen.add(ticker)
            tickers.append(ticker)
        return tickers

    for sec_tickers in universe.values():
        for ticker in sec_tickers[:SCREENER_MAX_PER_SECTOR]:
            if ticker in seen:
                continue
            seen.add(ticker)
            tickers.append(ticker)
            if len(tickers) >= SCREENER_MAX_CANDIDATES:
                return tickers

    return tickers


def _needs_enrichment(
    *,
    pe_min: float | None,
    pe_max: float | None,
    pb_max: float | None,
    dividend_yield_min: float | None,
    beta_max: float | None,
    pct_from_52w_high_min: float | None,
    pct_from_52w_high_max: float | None,
    revenue_growth_min: float | None,
    roe_min: float | None,
    debt_to_equity_max: float | None,
    avg_volume_min: float | None,
    profitable_only: bool,
    score_min: float | None,
    sort_by: str,
) -> bool:
    info_filters = [
        pe_min,
        pe_max,
        pb_max,
        dividend_yield_min,
        beta_max,
        pct_from_52w_high_min,
        pct_from_52w_high_max,
        revenue_growth_min,
        roe_min,
        debt_to_equity_max,
        avg_volume_min,
        score_min,
    ]
    if profitable_only:
        return True
    if any(value is not None for value in info_filters):
        return True
    return sort_by not in {"market_cap", "current_price", "change_pct"}


def _build_snapshot_result(snapshot: dict, *, ticker: str, sector: str, country: str) -> dict | None:
    current_price = float(snapshot.get("current_price") or snapshot.get("price") or 0.0)
    if current_price <= 0:
        return None
    prev_close = float(snapshot.get("prev_close") or current_price)
    change_pct = float(snapshot.get("change_pct") or (((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0))
    return {
        "ticker": ticker,
        "name": snapshot.get("name") or ticker,
        "sector": sector,
        "industry": "N/A",
        "market_cap": float(snapshot.get("market_cap") or 0.0),
        "current_price": round(current_price, 2),
        "change_pct": round(change_pct, 2),
        "pe_ratio": None,
        "pb_ratio": None,
        "dividend_yield": None,
        "beta": None,
        "week52_high": None,
        "week52_low": None,
        "pct_from_52w_high": None,
        "revenue_growth": None,
        "roe": None,
        "debt_to_equity": None,
        "avg_volume": None,
        "profit_margins": None,
        "score": None,
        "country_code": country,
    }


def _find_owning_sector(universe: dict[str, list[str]], ticker: str, sector: str | None) -> str:
    if sector:
        return sector
    return next(
        (sector_name for sector_name, sector_tickers in universe.items() if ticker in sector_tickers),
        "N/A",
    )


def _filter_snapshot_results(
    results: list[dict],
    *,
    market_cap_min: float | None,
    market_cap_max: float | None,
    price_min: float | None,
    price_max: float | None,
    change_pct_min: float | None,
    change_pct_max: float | None,
) -> list[dict]:
    filtered_results: list[dict] = []
    for item in results:
        market_cap = float(item.get("market_cap") or 0.0)
        current_price = float(item.get("current_price") or 0.0)
        change_pct = float(item.get("change_pct") or 0.0)

        if market_cap_min and market_cap < market_cap_min:
            continue
        if market_cap_max and market_cap > market_cap_max:
            continue
        if price_min and current_price < price_min:
            continue
        if price_max and current_price > price_max:
            continue
        if change_pct_min is not None and change_pct < change_pct_min:
            continue
        if change_pct_max is not None and change_pct > change_pct_max:
            continue
        filtered_results.append(item)
    return filtered_results


def _sort_screened_results(results: list[dict], *, sort_by: str, sort_dir: str, limit: int) -> list[dict]:
    reverse = sort_dir == "desc"
    sort_key = sort_by if sort_by in ALLOWED_SORT_FIELDS else "market_cap"
    results.sort(key=lambda x: x.get(sort_key) or 0, reverse=reverse)
    return results[:limit]


def _with_screener_partial(payload: dict, *, fallback_reason: str) -> dict:
    response = dict(payload)
    response["partial"] = True
    response["fallback_reason"] = fallback_reason
    return response


def _allow_public_screener_warmup() -> bool:
    return not settings.startup_memory_safe_mode


def _maybe_trim_public_route_memory(reason: str) -> None:
    try:
        maybe_trim_process_memory(reason)
    except Exception as exc:
        logging.debug("memory trim skipped for %s: %s", reason, exc)


def _spawn_screener_cache_warmup(cache_key: str, fetcher) -> None:
    if not _allow_public_screener_warmup():
        return

    async def _warm() -> None:
        try:
            await cache.get_or_fetch(cache_key, fetcher, ttl=SCREENER_RESPONSE_CACHE_TTL)
        except Exception as exc:
            logging.warning("screener cache warmup failed for %s: %s", cache_key, exc)

    _, created = get_or_create_background_job(f"screener_cache_warmup:{cache_key}", _warm)
    if not created:
        logging.info("screener cache warmup already running for %s; reusing existing task", cache_key)


async def _build_kr_bulk_snapshot_results(
    *,
    tickers: list[str],
    universe: dict[str, list[str]],
    sector: str | None,
    country: str,
    skip_full_market_fallback: bool = False,
) -> list[dict]:
    quotes = await kr_market_quote_client.get_kr_bulk_quotes(
        tickers,
        skip_full_market_fallback=skip_full_market_fallback,
    )
    results: list[dict] = []
    for ticker in tickers:
        quote = quotes.get(ticker)
        if not quote:
            continue
        owning_sector = _find_owning_sector(universe, ticker, sector)
        result = _build_snapshot_result(
            {
                "current_price": quote.get("current_price"),
                "price": quote.get("current_price"),
                "prev_close": quote.get("prev_close"),
                "change_pct": quote.get("change_pct"),
                "market_cap": quote.get("market_cap"),
                "name": quote.get("name") or ticker,
            },
            ticker=ticker,
            sector=owning_sector,
            country=country,
        )
        if result is not None:
            results.append(result)
    return results


async def _build_kr_representative_snapshot_results(
    *,
    limit: int,
    universe: dict[str, list[str]],
    sector: str | None,
    country: str,
) -> list[dict]:
    quotes = await kr_market_quote_client.get_kr_representative_quotes(limit=max(limit, SCREENER_COLD_START_KR_CANDIDATES))
    results: list[dict] = []
    for ticker, quote in quotes.items():
        owning_sector = _find_owning_sector(universe, ticker, sector)
        if sector and owning_sector != sector:
            continue
        result = _build_snapshot_result(
            {
                "current_price": quote.get("current_price"),
                "price": quote.get("current_price"),
                "prev_close": quote.get("prev_close"),
                "change_pct": quote.get("change_pct"),
                "market_cap": quote.get("market_cap"),
                "name": quote.get("name") or ticker,
            },
            ticker=ticker,
            sector=owning_sector,
            country=country,
        )
        if result is not None:
            results.append(result)
    return results


async def _build_snapshot_fallback(
    *,
    country: str,
    sector: str | None,
    limit: int,
) -> dict:
    universe = await get_universe(country, prefer_fallback=(country == "KR"))
    selected = _select_candidate_tickers(universe, sector)[: max(limit, 10)]

    if country == "KR":
        results = (await _build_kr_bulk_snapshot_results(
            tickers=selected,
            universe=universe,
            sector=sector,
            country=country,
            skip_full_market_fallback=True,
        ))[:limit]
        return _with_screener_partial(
            {
                "results": results,
                "total": len(results),
                "sectors": list(universe.keys()),
            },
            fallback_reason="kr_bulk_snapshot_only",
        )

    async def _snapshot_only(ticker: str):
        try:
            snapshot = await asyncio.wait_for(
                yfinance_client.get_market_snapshot(ticker, period="3mo"),
                timeout=3,
            )
        except Exception as exc:
            logging.warning("screener fallback snapshot failed for %s: %s", ticker, exc)
            return None
        if not snapshot.get("valid"):
            return None
        owning_sector = sector or next(
            (sector_name for sector_name, sector_tickers in universe.items() if ticker in sector_tickers),
            "N/A",
        )
        return _build_snapshot_result(snapshot, ticker=ticker, sector=owning_sector, country=country)

    snapshots = await gather_limited(selected, _snapshot_only, limit=SCREENER_CONCURRENCY)
    results = [item for item in snapshots if not isinstance(item, Exception) and item is not None][:limit]
    return _with_screener_partial(
        {
            "results": results,
            "total": len(results),
            "sectors": list(universe.keys()),
        },
        fallback_reason="snapshot_only",
    )


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
    cache_key = _build_screener_cache_key(
        country=country,
        sector=sector,
        market_cap_min=market_cap_min,
        market_cap_max=market_cap_max,
        price_min=price_min,
        price_max=price_max,
        pe_min=pe_min,
        pe_max=pe_max,
        pb_max=pb_max,
        dividend_yield_min=dividend_yield_min,
        beta_max=beta_max,
        change_pct_min=change_pct_min,
        change_pct_max=change_pct_max,
        pct_from_52w_high_min=pct_from_52w_high_min,
        pct_from_52w_high_max=pct_from_52w_high_max,
        revenue_growth_min=revenue_growth_min,
        roe_min=roe_min,
        debt_to_equity_max=debt_to_equity_max,
        avg_volume_min=avg_volume_min,
        profitable_only=profitable_only,
        score_min=score_min,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
    )
    needs_enrichment = _needs_enrichment(
        pe_min=pe_min,
        pe_max=pe_max,
        pb_max=pb_max,
        dividend_yield_min=dividend_yield_min,
        beta_max=beta_max,
        pct_from_52w_high_min=pct_from_52w_high_min,
        pct_from_52w_high_max=pct_from_52w_high_max,
        revenue_growth_min=revenue_growth_min,
        roe_min=roe_min,
        debt_to_equity_max=debt_to_equity_max,
        avg_volume_min=avg_volume_min,
        profitable_only=profitable_only,
        score_min=score_min,
        sort_by=sort_by,
    )

    async def _screen_ticker(ticker: str):
        try:
            snapshot = await asyncio.wait_for(
                yfinance_client.get_market_snapshot(ticker, period="6mo"),
                timeout=4,
            )
            if not snapshot.get("valid"):
                return None

            owning_sector = sector or next(
                (sector_name for sector_name, sector_tickers in universe.items() if ticker in sector_tickers),
                "N/A",
            )

            if not needs_enrichment:
                market_cap = float(snapshot.get("market_cap") or 0.0)
                current_price = float(snapshot.get("current_price") or snapshot.get("price") or 0.0)
                prev_close = float(snapshot.get("prev_close") or current_price)
                change_pct = float(snapshot.get("change_pct") or (((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0))

                if market_cap_min and market_cap < market_cap_min:
                    return None
                if market_cap_max and market_cap > market_cap_max:
                    return None
                if price_min and current_price < price_min:
                    return None
                if price_max and current_price > price_max:
                    return None
                if change_pct_min is not None and change_pct < change_pct_min:
                    return None
                if change_pct_max is not None and change_pct > change_pct_max:
                    return None

                return _build_snapshot_result(snapshot, ticker=ticker, sector=owning_sector, country=country)

            info = await asyncio.wait_for(yfinance_client.get_stock_info(ticker), timeout=4)
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
                "sector": info.get("sector") or owning_sector,
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

    async def _load_universe() -> dict[str, list[str]]:
        nonlocal universe
        if not universe:
            universe = await get_universe(country, prefer_fallback=(country == "KR"))
        return universe

    async def _build_response(
        *,
        candidate_limit: int | None = None,
        partial: bool = False,
        fallback_reason: str | None = None,
    ):
        current_universe = await _load_universe()
        tickers = _select_candidate_tickers(current_universe, sector)
        if not needs_enrichment and country == "KR":
            if candidate_limit is None:
                tickers = tickers[: max(limit, 10)]
            else:
                tickers = tickers[:candidate_limit]
            bulk_results = await _build_kr_bulk_snapshot_results(
                tickers=tickers,
                universe=current_universe,
                sector=sector,
                country=country,
                skip_full_market_fallback=True,
            )
            filtered_results = _filter_snapshot_results(
                bulk_results,
                market_cap_min=market_cap_min,
                market_cap_max=market_cap_max,
                price_min=price_min,
                price_max=price_max,
                change_pct_min=change_pct_min,
                change_pct_max=change_pct_max,
            )
            response = {
                "results": _sort_screened_results(filtered_results, sort_by=sort_by, sort_dir=sort_dir, limit=limit),
                "total": len(filtered_results[:limit]),
                "sectors": list(current_universe.keys()),
            }
            if partial:
                return _with_screener_partial(
                    response,
                    fallback_reason=fallback_reason or "kr_bulk_snapshot_warming",
                )
            return response

        if needs_enrichment:
            tickers = tickers[: max(limit * 2, SCREENER_ENRICHMENT_BUDGET)]
        screened = await gather_limited(tickers, _screen_ticker, limit=SCREENER_CONCURRENCY)
        results = [item for item in screened if not isinstance(item, Exception) and item is not None]

        results = _sort_screened_results(results, sort_by=sort_by, sort_dir=sort_dir, limit=limit)

        return {
            "results": results,
            "total": len(results),
            "sectors": list(current_universe.keys()),
        }

    universe: dict[str, list[str]] = {}
    use_direct_kr_quick_path = country == "KR" and not needs_enrichment
    try:
        if use_direct_kr_quick_path:
            current_universe = await _load_universe()
            selected_tickers = _select_candidate_tickers(current_universe, sector)
            should_use_cold_start_partial = limit > SCREENER_COLD_START_KR_CANDIDATES and len(selected_tickers) > SCREENER_COLD_START_KR_CANDIDATES
            if should_use_cold_start_partial:
                cached_response = await cache.get(cache_key)
                if cached_response is not None:
                    _maybe_trim_public_route_memory("screener")
                    return cached_response
                representative_results = await _build_kr_representative_snapshot_results(
                    limit=limit,
                    universe=current_universe,
                    sector=sector,
                    country=country,
                )
                filtered_representative_results = _filter_snapshot_results(
                    representative_results,
                    market_cap_min=market_cap_min,
                    market_cap_max=market_cap_max,
                    price_min=price_min,
                    price_max=price_max,
                    change_pct_min=change_pct_min,
                    change_pct_max=change_pct_max,
                )
                if filtered_representative_results:
                    response = _with_screener_partial(
                        {
                            "results": _sort_screened_results(
                                filtered_representative_results,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                limit=limit,
                            ),
                            "total": len(filtered_representative_results[:limit]),
                            "sectors": list(current_universe.keys()),
                        },
                        fallback_reason="kr_representative_snapshot_warming",
                    )
                    _spawn_screener_cache_warmup(cache_key, _build_response)
                    _maybe_trim_public_route_memory("screener")
                    return response
                response = await asyncio.wait_for(
                    _build_response(
                        candidate_limit=SCREENER_COLD_START_KR_CANDIDATES,
                        partial=True,
                        fallback_reason="kr_bulk_snapshot_warming",
                    ),
                    timeout=PUBLIC_SCREENER_TIMEOUT_SECONDS,
                )
                _spawn_screener_cache_warmup(cache_key, _build_response)
            else:
                response = await asyncio.wait_for(
                    _build_response(),
                    timeout=PUBLIC_SCREENER_TIMEOUT_SECONDS,
                )
        else:
            response = await asyncio.wait_for(
                cache.get_or_fetch(
                    cache_key,
                    _build_response,
                    ttl=SCREENER_RESPONSE_CACHE_TTL,
                ),
                timeout=PUBLIC_SCREENER_TIMEOUT_SECONDS,
            )
    except asyncio.TimeoutError:
        err = SP_5018(f"Screener for {country} exceeded {PUBLIC_SCREENER_TIMEOUT_SECONDS} seconds.")
        err.log("warning")
        response = await _build_snapshot_fallback(country=country, sector=sector, limit=limit)
        _maybe_trim_public_route_memory("screener")
        return response

    _maybe_trim_public_route_memory("screener")
    return response
