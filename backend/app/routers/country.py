import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from app.models.country import COUNTRY_REGISTRY
from app.data import kr_market_quote_client, yfinance_client
from app.analysis.country_analyzer import analyze_country
from app.analysis.forecast_engine import forecast_index
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.scoring.country_scorer import build_country_score
from app.scoring.fear_greed import calculate_fear_greed
from app.services import archive_service, export_service, market_service
from app.errors import SP_6001, SP_3001, SP_3004, SP_5002, SP_5004, SP_2005, SP_5018
from app.utils.async_tools import gather_limited

router = APIRouter(prefix="/api", tags=["country"])
PUBLIC_ENDPOINT_TIMEOUT_SECONDS = 18
OPPORTUNITY_TIMEOUT_SECONDS = 12
OPPORTUNITY_QUICK_TIMEOUT_SECONDS = 8
HEATMAP_TIMEOUT_SECONDS = 10
HEATMAP_TICKERS_PER_SECTOR = 2
HEATMAP_CHILDREN_PER_SECTOR = 2
HEATMAP_CONCURRENCY = 2


async def _load_market_snapshot(ticker: str, *, period: str = "6mo") -> dict | None:
    try:
        snapshot = await yfinance_client.get_market_snapshot(ticker, period=period)
    except Exception as exc:
        logging.warning("market snapshot fetch failed for %s: %s", ticker, exc)
        return None
    if not snapshot or not snapshot.get("valid"):
        return None
    return snapshot


async def _build_heatmap_payload(code: str) -> dict:
    from app.data.universe_data import get_universe

    universe = await get_universe(code)

    sectors = []
    for sector_name, tickers in universe.items():
        fetched = await gather_limited(
            tickers[:HEATMAP_TICKERS_PER_SECTOR],
            lambda ticker: _load_market_snapshot(ticker, period="6mo"),
            limit=HEATMAP_CONCURRENCY,
        )
        stocks = []
        for item in fetched:
            if not isinstance(item, dict):
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
            sectors.append({"name": sector_name, "children": stocks[:HEATMAP_CHILDREN_PER_SECTOR]})

    return {"children": sectors}


async def _build_heatmap_fallback(code: str) -> dict:
    from app.data.universe_data import get_universe

    universe = await get_universe(code)
    max_sector_size = max((len(tickers) for tickers in universe.values()), default=1)
    sectors = []
    for sector_name, tickers in universe.items():
        if not tickers:
            continue
        children = []
        for idx, ticker in enumerate(tickers[:HEATMAP_CHILDREN_PER_SECTOR], start=1):
            relative_size = max(len(tickers) - idx + 1, 1) / max(max_sector_size, 1)
            children.append(
                {
                    "name": ticker.split(".")[0],
                    "ticker": ticker,
                    "fullName": ticker,
                    "size": round(relative_size * 1_000_000_000, 2),
                    "change": 0.0,
                }
            )
        sectors.append({"name": sector_name, "children": children})
    return {
        "children": sectors,
        "partial": True,
        "fallback_reason": "live_snapshot_timeout",
    }


def _log_background_completion(task: asyncio.Task, *, label: str) -> None:
    if task.cancelled():
        logging.info("%s background task was cancelled.", label)
        return
    try:
        task.result()
    except Exception as exc:
        logging.warning("%s background task failed: %s", label, exc, exc_info=True)


def _cancel_background_task(task: asyncio.Task, *, label: str) -> None:
    if task.done():
        return
    task.cancel()
    logging.info("%s background task cancelled after fallback response.", label)


def _with_opportunity_partial(
    payload: dict,
    *,
    fallback_reason: str,
    note: str | None = None,
    fallback_tier: str | None = None,
) -> dict:
    response = dict(payload)
    response["partial"] = True
    response["fallback_reason"] = fallback_reason
    if fallback_tier:
        response["fallback_tier"] = fallback_tier
    if note:
        existing_note = str(response.get("universe_note") or "").strip()
        response["universe_note"] = " ".join(part for part in [existing_note, note.strip()] if part).strip()
    return response


def _empty_institutional_analysis() -> dict:
    return {
        "policy_institutions": [],
        "sell_side": [],
        "policy_sellside_aligned": False,
        "consensus_count": 0,
        "consensus_summary": "정밀 기관 해석이 아직 준비되지 않아 1차 시장 스냅샷을 먼저 제공합니다.",
    }


def _build_top_stock_refs(opportunities: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for rank, item in enumerate(opportunities[:5], start=1):
        refs.append(
            {
                "rank": rank,
                "ticker": item.get("ticker", ""),
                "name": item.get("name") or item.get("ticker", ""),
                "score": round(float(item.get("opportunity_score") or 0.0), 1),
                "current_price": round(float(item.get("current_price") or 0.0), 2),
                "change_pct": round(float(item.get("change_pct") or 0.0), 2),
                "reason": (item.get("execution_note") or (item.get("thesis") or [""])[0] or "").strip(),
            }
        )
    return refs


async def _build_country_report_fallback(
    code: str,
    *,
    reason: str,
    error_code: str,
    detail: str,
) -> dict:
    country = COUNTRY_REGISTRY[code]
    primary_index = country.indices[0]
    primary_index_history = await yfinance_client.get_price_history(primary_index.ticker, period="6mo")

    market_quotes = await asyncio.gather(
        *(yfinance_client.get_index_quote(idx.ticker) for idx in country.indices),
        return_exceptions=True,
    )
    market_data = {}
    for idx, quote in zip(country.indices, market_quotes):
        if isinstance(quote, Exception):
            SP_2005(idx.ticker).log("warning")
            market_data[idx.name] = {"price": 0, "change_pct": 0}
        else:
            market_data[idx.name] = quote

    fear_greed = calculate_fear_greed(primary_index_history, country_code=code)
    next_day = forecast_next_day(
        ticker=primary_index.ticker,
        name=primary_index.name,
        country_code=code,
        price_history=primary_index_history,
        benchmark_history=primary_index_history,
        asset_type="index",
    )
    market_regime = build_market_regime(
        country_code=code,
        name=primary_index.name,
        price_history=primary_index_history,
        fear_greed=fear_greed,
        next_day_forecast=next_day,
    )
    forecast = await forecast_index(
        primary_index.ticker,
        primary_index.name,
        {},
        "",
        price_history=primary_index_history,
        benchmark_history=primary_index_history,
    )

    quick_opportunities: list[dict] = []
    try:
        quick_response = await asyncio.wait_for(
            market_service.get_market_opportunities_quick(code, limit=5),
            timeout=max(3.0, min(OPPORTUNITY_QUICK_TIMEOUT_SECONDS, 6.0)),
        )
        quick_opportunities = list(quick_response.get("opportunities") or [])
    except Exception as exc:
        logging.warning("country report fallback quick candidates failed for %s: %s", code, exc, exc_info=True)

    market_summary = (
        f"{country.name_local} 정밀 시장 리포트 생성이 길어져 1차 시장 스냅샷을 먼저 제공합니다. "
        "대표 지수 흐름과 상위 후보는 바로 확인할 수 있고, 잠시 뒤 다시 열면 기관·뉴스 해석이 반영된 정밀 리포트로 회복될 수 있습니다."
    )
    if detail:
        market_summary = f"{market_summary} {detail}"

    return {
        "country": country.model_dump(),
        "score": build_country_score({}).model_dump(),
        "market_summary": market_summary,
        "macro_claims": [],
        "key_news": [],
        "institutional_analysis": _empty_institutional_analysis(),
        "top_stocks": _build_top_stock_refs(quick_opportunities),
        "fear_greed": fear_greed.model_dump(),
        "forecast": forecast.model_dump(),
        "next_day_forecast": next_day.model_dump(),
        "market_regime": market_regime.model_dump(),
        "primary_index_history": primary_index_history,
        "market_data": market_data,
        "llm_available": False,
        "errors": [error_code],
        "partial": True,
        "fallback_reason": reason,
        "generated_at": datetime.now().isoformat(),
    }


async def _load_country_report_with_fallback(
    code: str,
    *,
    timeout_seconds: float,
    keep_background: bool,
) -> tuple[dict, bool]:
    if keep_background:
        report_task = asyncio.create_task(analyze_country(code))
        report_task.add_done_callback(
            lambda task, label=f"Country report for {code}": _log_background_completion(task, label=label)
        )
        try:
            report = await asyncio.wait_for(asyncio.shield(report_task), timeout=timeout_seconds)
            return report, False
        except asyncio.TimeoutError:
            detail = (
                f"{code} 국가 리포트 계산이 길어지고 있어 1차 보고서를 먼저 제공합니다. "
                "백그라운드 계산은 계속 진행되니 잠시 뒤 다시 열면 정밀 리포트가 바로 보일 수 있습니다."
            )
            return (
                await _build_country_report_fallback(
                    code,
                    reason="country_report_timeout",
                    error_code="SP-5018",
                    detail=detail,
                ),
                True,
            )
        except Exception as exc:
            logging.warning("country report failed for %s: %s", code, exc, exc_info=True)
            return (
                await _build_country_report_fallback(
                    code,
                    reason="country_report_error",
                    error_code="SP-3001",
                    detail="정밀 리포트 생성 중 오류가 발생해 1차 시장 스냅샷으로 우선 전환했습니다.",
                ),
                True,
            )

    try:
        report = await asyncio.wait_for(analyze_country(code), timeout=timeout_seconds)
        return report, False
    except asyncio.TimeoutError:
        return (
            await _build_country_report_fallback(
                code,
                reason="country_report_timeout",
                error_code="SP-5018",
                detail="내보내기용 정밀 리포트 생성이 길어져 1차 시장 스냅샷 기반 보고서를 대신 생성했습니다.",
            ),
            True,
        )
    except Exception as exc:
        logging.warning("country report export load failed for %s: %s", code, exc, exc_info=True)
        return (
            await _build_country_report_fallback(
                code,
                reason="country_report_error",
                error_code="SP-5004",
                detail="내보내기용 정밀 리포트 생성 중 오류가 발생해 1차 시장 스냅샷 기반 보고서를 대신 생성했습니다.",
            ),
            True,
        )


async def _build_sector_performance_payload(code: str) -> list[dict]:
    from app.data.universe_data import get_universe

    universe = await get_universe(code)

    if code == "KR":
        sector_candidates = {
            sector_name: tickers[:8]
            for sector_name, tickers in universe.items()
            if tickers
        }
        requested = [ticker for tickers in sector_candidates.values() for ticker in tickers]
        quotes = await kr_market_quote_client.get_kr_bulk_quotes(requested)
        results = []
        for sector_name, tickers in sector_candidates.items():
            valid = [quotes[ticker] for ticker in tickers if ticker in quotes]
            if not valid:
                continue
            leader = max(valid, key=lambda item: float(item.get("market_cap") or item.get("current_price") or 0.0))
            avg_change = sum(float(item.get("change_pct") or 0.0) for item in valid) / len(valid)
            results.append(
                {
                    "sector": sector_name,
                    "ticker": leader["ticker"],
                    "price": round(float(leader.get("current_price") or 0.0), 2),
                    "change_pct": round(avg_change, 2),
                    "breadth": len(valid),
                    "leader_name": leader.get("name", leader["ticker"]),
                }
            )
        results.sort(key=lambda item: item["change_pct"], reverse=True)
        return results

    results = []
    for sector_name, tickers in universe.items():
        fetched = await gather_limited(tickers[:8], lambda ticker: _load_market_snapshot(ticker, period="6mo"), limit=4)
        valid = [item for item in fetched if not isinstance(item, Exception) and item is not None]
        if not valid:
            continue

        leader = max(valid, key=lambda item: float(item.get("market_cap") or item.get("current_price") or 0.0))
        avg_change = sum(float(item.get("change_pct") or 0.0) for item in valid) / len(valid)
        results.append(
            {
                "sector": sector_name,
                "ticker": leader["ticker"],
                "price": round(float(leader.get("price") or 0.0), 2),
                "change_pct": round(avg_change, 2),
                "breadth": len(valid),
                "leader_name": leader.get("name", leader["ticker"]),
            }
        )

    results.sort(key=lambda item: item["change_pct"], reverse=True)
    return results


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
        report, partial = await _load_country_report_with_fallback(
            code,
            timeout_seconds=PUBLIC_ENDPOINT_TIMEOUT_SECONDS,
            keep_background=True,
        )
    except Exception as e:
        err = SP_3001(code)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    if not partial:
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
    cache_key = f"heatmap:v3:{code}"

    async def _fetch_heatmap():
        try:
            return await asyncio.wait_for(_build_heatmap_payload(code), timeout=HEATMAP_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            err = SP_5018(f"Heatmap for {code} exceeded {HEATMAP_TIMEOUT_SECONDS} seconds.")
            err.log("warning")
            return await _build_heatmap_fallback(code)

    return await data_cache.get_or_fetch(cache_key, _fetch_heatmap, ttl=900)


@router.get("/country/{code}/report/pdf")
async def download_country_report_pdf(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    try:
        report, _ = await _load_country_report_with_fallback(
            code,
            timeout_seconds=PUBLIC_ENDPOINT_TIMEOUT_SECONDS,
            keep_background=False,
        )
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
        report, _ = await _load_country_report_with_fallback(
            code,
            timeout_seconds=PUBLIC_ENDPOINT_TIMEOUT_SECONDS,
            keep_background=False,
        )
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
    """Korean market indicators for the dashboard."""
    from app.data import cache as data_cache
    cached = await data_cache.get("market_indicators")
    if cached:
        return cached

    indicators = []
    tickers = {
        "USD/KRW": "USDKRW=X",
        "Gold": "GC=F",
        "Oil (WTI)": "CL=F",
        "Bitcoin": "BTC-USD",
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
    """Sector performance heatmap data using live sector constituents."""
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    from app.data import cache as data_cache
    cache_key = f"sector_perf:v3:{code}"

    async def _fetch_sector_performance():
        return await _build_sector_performance_payload(code)

    return await data_cache.get_or_fetch(cache_key, _fetch_sector_performance, ttl=300)


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
    radar_label = f"Opportunity radar for {code}"
    quick_label = f"Opportunity quick fallback for {code}"
    opportunity_task = asyncio.create_task(market_service.get_market_opportunities(code, limit))
    opportunity_task.add_done_callback(
        lambda task, label=radar_label: _log_background_completion(task, label=label)
    )
    quick_task = asyncio.create_task(market_service.get_market_opportunities_quick(code, limit))
    quick_task.add_done_callback(
        lambda task, label=quick_label: _log_background_completion(task, label=label)
    )
    try:
        response = await asyncio.wait_for(
            asyncio.shield(opportunity_task),
            timeout=OPPORTUNITY_TIMEOUT_SECONDS,
        )
        _cancel_background_task(quick_task, label=quick_label)
        return response
    except asyncio.TimeoutError:
        try:
            quick_response = await asyncio.wait_for(
                asyncio.shield(quick_task),
                timeout=max(2.0, min(OPPORTUNITY_QUICK_TIMEOUT_SECONDS, 4.0)),
            )
            _cancel_background_task(opportunity_task, label=radar_label)
            return _with_opportunity_partial(
                quick_response,
                fallback_reason="opportunity_quick_response",
            )
        except asyncio.TimeoutError:
            logging.warning("opportunity quick fallback timed out for %s", code)
            _cancel_background_task(opportunity_task, label=radar_label)
            _cancel_background_task(quick_task, label=quick_label)
            cached_quick = await market_service.get_cached_market_opportunities_quick(code, limit)
            if cached_quick:
                return _with_opportunity_partial(
                    cached_quick,
                    fallback_reason="opportunity_cached_quick_response",
                    note="이번 응답에서는 최근 usable 후보를 먼저 표시합니다.",
                    fallback_tier="cached_quick",
                )
            return _with_opportunity_partial(
                market_service.build_market_opportunities_placeholder(
                    code,
                    note=(
                        f"{code} 기회 레이더가 이번 요청에서 사용 가능한 후보를 만들지 못했습니다. "
                        "자동 장기 스캔이 계속 유지되는 상태는 아니며, 다음 재조회에서는 quick 스냅샷을 새로 시도합니다."
                    ),
                ),
                fallback_reason="opportunity_placeholder_response",
            )
        except Exception as quick_exc:
            logging.warning("opportunity quick fallback failed for %s: %s", code, quick_exc, exc_info=True)
            _cancel_background_task(opportunity_task, label=radar_label)
            _cancel_background_task(quick_task, label=quick_label)
            cached_quick = await market_service.get_cached_market_opportunities_quick(code, limit)
            if cached_quick:
                return _with_opportunity_partial(
                    cached_quick,
                    fallback_reason="opportunity_cached_quick_response",
                    note="이번 응답에서는 최근 usable 후보를 먼저 표시합니다.",
                    fallback_tier="cached_quick",
                )
            return _with_opportunity_partial(
                market_service.build_market_opportunities_placeholder(
                    code,
                    note=(
                        f"{code} 기회 레이더가 이번 요청에서 사용 가능한 후보를 만들지 못했습니다. "
                        "잠시 뒤 다시 열면 fresh quick 스냅샷을 새로 시도합니다."
                    ),
                ),
                fallback_reason="opportunity_placeholder_response",
            )
