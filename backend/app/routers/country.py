import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from app.models.country import COUNTRY_REGISTRY
from app.data import yfinance_client
from app.analysis.country_analyzer import analyze_country
from app.analysis.forecast_engine import forecast_index
from app.services import archive_service, export_service, market_service
from app.errors import SP_6001, SP_3001, SP_3004, SP_5002, SP_5004, SP_2005
from app.utils.async_tools import gather_limited

router = APIRouter(prefix="/api", tags=["country"])


async def _load_market_snapshot(ticker: str, *, period: str = "6mo") -> dict | None:
    try:
        snapshot = await yfinance_client.get_market_snapshot(ticker, period=period)
    except Exception as exc:
        logging.warning("market snapshot fetch failed for %s: %s", ticker, exc)
        return None
    if not snapshot or not snapshot.get("valid"):
        return None
    return snapshot


@router.get("/countries")
async def list_countries():
    results = []
    for code, info in COUNTRY_REGISTRY.items():
        indices_data = []
        for idx in info.indices:
            try:
                q = await yfinance_client.get_index_quote(idx.ticker)
            except Exception:
                SP_2005(idx.ticker).log()
                q = {"price": 0, "change_pct": 0}
            indices_data.append({
                "ticker": idx.ticker,
                "name": idx.name,
                "price": q.get("price", 0),
                "change_pct": q.get("change_pct", 0),
            })
        results.append({
            "code": code,
            "name": info.name,
            "name_local": info.name_local,
            "currency": info.currency,
            "indices": indices_data,
        })
    return results


@router.get("/country/{code}/report")
async def get_country_report(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report = await analyze_country(code)
    except Exception as e:
        err = SP_3001(code)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    try:
        await archive_service.save_report("country", report, country_code=code)
    except Exception as e:
        SP_5002(str(e)[:100]).log()

    return report


@router.get("/country/{code}/heatmap")
async def get_heatmap(code: str):
    """Treemap heatmap data: sector > stocks with market_cap and change_pct."""
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    from app.data import cache as data_cache
    cache_key = f"heatmap:{code}"
    cached = await data_cache.get(cache_key)
    if cached:
        return cached

    from app.data.universe_data import get_universe
    universe = await get_universe(code)

    sectors = []
    for sector_name, tickers in universe.items():
        fetched = await gather_limited(tickers[:10], lambda ticker: _load_market_snapshot(ticker, period="6mo"), limit=4)
        stocks = []
        for item in fetched:
            if isinstance(item, Exception) or item is None:
                continue
            stocks.append({
                "name": item["ticker"].split(".")[0],
                "ticker": item["ticker"],
                "fullName": item.get("name", item["ticker"]),
                "size": item.get("market_cap", 0),
                "change": item.get("change_pct", 0),
            })
        if stocks:
            stocks.sort(key=lambda s: s["size"], reverse=True)
            sectors.append({"name": sector_name, "children": stocks[:8]})

    result = {"children": sectors}
    await data_cache.set(cache_key, result, 900)
    return result


@router.get("/country/{code}/report/pdf")
async def download_country_report_pdf(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report = await analyze_country(code)
        country_name = COUNTRY_REGISTRY[code].name_local or COUNTRY_REGISTRY[code].name
        pdf_bytes = export_service.export_pdf(report, title=f"{country_name} Market Report")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={code}_report.pdf"},
        )
    except Exception as e:
        err = SP_5004(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/country/{code}/report/csv")
async def download_country_report_csv(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report = await analyze_country(code)
        csv_content = export_service.export_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={code}_report.csv"},
        )
    except Exception as e:
        err = SP_5004(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/country/{code}/forecast")
async def get_country_forecast(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        primary = country.indices[0]
        forecast = await forecast_index(primary.ticker, primary.name, {}, "")
        return forecast
    except Exception as e:
        err = SP_3004(str(e)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/market/indicators")
async def get_market_indicators():
    """Global market indicators for the dashboard."""
    from app.data import cache as data_cache
    cached = await data_cache.get("market_indicators")
    if cached:
        return cached

    indicators = []
    tickers = {
        "VIX": "^VIX", "DXY": "DX-Y.NYB", "Gold": "GC=F", "Oil (WTI)": "CL=F",
        "US 10Y": "^TNX", "Bitcoin": "BTC-USD",
        "USD/KRW": "USDKRW=X", "USD/JPY": "USDJPY=X", "EUR/USD": "EURUSD=X",
    }
    for name, ticker in tickers.items():
        try:
            q = await yfinance_client.get_index_quote(ticker)
            indicators.append({"name": name, "price": q.get("price", 0), "change_pct": q.get("change_pct", 0)})
        except Exception:
            indicators.append({"name": name, "price": 0, "change_pct": 0})

    await data_cache.set("market_indicators", indicators, 300)
    return indicators


@router.get("/country/{code}/sector-performance")
async def get_sector_performance(code: str):
    """Sector performance heatmap data using sector ETFs."""
    code = code.upper()
    from app.data import cache as data_cache
    cache_key = f"sector_perf:{code}"
    cached = await data_cache.get(cache_key)
    if cached:
        return cached

    sector_etfs = {
        "US": {
            "Energy": "XLE", "Materials": "XLB", "Industrials": "XLI",
            "Consumer Disc.": "XLY", "Consumer Stap.": "XLP", "Health Care": "XLV",
            "Financials": "XLF", "IT": "XLK", "Communication": "XLC",
            "Utilities": "XLU", "Real Estate": "XLRE",
        },
        "KR": {
            "KOSPI 200": "069500.KS", "IT": "091160.KS", "Financials": "091170.KS",
            "Industrials": "091180.KS", "Health Care": "227540.KS",
            "Consumer": "098560.KS", "Materials": "091220.KS",
        },
        "JP": {
            "TOPIX": "1306.T", "Nikkei 225": "1321.T",
            "Banks": "1615.T", "IT": "1627.T",
        },
    }
    etfs = sector_etfs.get(code, {})
    results = []
    for sector_name, etf_ticker in etfs.items():
        try:
            q = await yfinance_client.get_index_quote(etf_ticker)
            results.append({
                "sector": sector_name, "ticker": etf_ticker,
                "price": q.get("price", 0), "change_pct": q.get("change_pct", 0),
            })
        except Exception:
            results.append({"sector": sector_name, "ticker": etf_ticker, "price": 0, "change_pct": 0})

    await data_cache.set(cache_key, results, 300)
    return results


@router.get("/country/{code}/sectors")
async def list_sectors(code: str):
    code = code.upper()
    country = COUNTRY_REGISTRY.get(code)
    if not country:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    from app.data.yfinance_client import UNIVERSE
    universe = UNIVERSE.get(code, {})
    sectors = []
    for s in country.sectors_gics:
        tickers = universe.get(s, [])
        sectors.append({
            "id": s.lower().replace(" ", "_"),
            "name": s,
            "country_code": code,
            "stock_count": len(tickers),
        })
    return sectors


@router.get("/market/movers/{code}")
async def get_market_movers(code: str):
    """Top gainers and losers for a given market."""
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        return JSONResponse(status_code=404, content=SP_6001(code).to_dict())

    from app.data import cache as data_cache
    cache_key = f"movers:{code}"
    cached = await data_cache.get(cache_key)
    if cached:
        return cached

    from app.data.universe_data import get_universe
    universe = await get_universe(code)
    all_tickers = []
    seen = set()
    for sec_tickers in universe.values():
        for ticker in sec_tickers[:8]:
            if ticker in seen:
                continue
            seen.add(ticker)
            all_tickers.append(ticker)

    fetched = await gather_limited(all_tickers, lambda ticker: _load_market_snapshot(ticker, period="6mo"), limit=6)
    stocks = []
    for item in fetched:
        if isinstance(item, Exception) or item is None:
            continue
        stocks.append({
            "ticker": item["ticker"],
            "name": item.get("name", item["ticker"]),
            "price": round(item.get("price", 0), 2),
            "change_pct": round(item.get("change_pct", 0), 2),
        })

    stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    result = {
        "gainers": stocks[:5],
        "losers": list(reversed(stocks[-5:])) if len(stocks) >= 5 else list(reversed(stocks)),
    }
    await data_cache.set(cache_key, result, 900)
    return result


@router.get("/market/opportunities/{code}")
async def get_market_opportunities(code: str, limit: int = Query(12, ge=3, le=20)):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())
    return await market_service.get_market_opportunities(code, limit)
