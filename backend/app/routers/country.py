import asyncio
import logging
import math
import time
from collections.abc import Awaitable
from typing import Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from app.config import get_settings
from app.models.country import COUNTRY_REGISTRY
from app.data import kr_market_quote_client, yfinance_client
from app.analysis.country_analyzer import analyze_country
from app.analysis.forecast_engine import forecast_index
from app.scoring.country_scorer import build_country_score
from app.scoring.fear_greed import calculate_fear_greed
from app.runtime import get_or_create_background_job
from app.services import archive_service, export_service, market_service, prediction_capture_service, route_stability_service
from app.errors import SP_6001, SP_3001, SP_3004, SP_5002, SP_5004, SP_2005, SP_5018
from app.utils.async_tools import gather_limited
from app.utils.memory_hygiene import get_memory_pressure_snapshot, maybe_trim_process_memory
from app.utils import build_route_trace
from app.utils.market_calendar import market_session_cache_token

router = APIRouter(prefix="/api", tags=["country"])
settings = get_settings()
COUNTRY_REPORT_PUBLIC_TIMEOUT_SECONDS = 8
COUNTRY_REPORT_EXPORT_TIMEOUT_SECONDS = 18
COUNTRY_REPORT_FALLBACK_OPPORTUNITY_TIMEOUT_SECONDS = 1.0
OPPORTUNITY_TIMEOUT_SECONDS = 8
OPPORTUNITY_QUICK_TIMEOUT_SECONDS = 4
HEATMAP_TIMEOUT_SECONDS = 10
COUNTRIES_TIMEOUT_SECONDS = 6
COUNTRIES_WAIT_TIMEOUT_SECONDS = 2.5
COUNTRIES_CACHE_TTL_SECONDS = 300
COUNTRIES_LAST_SUCCESS_TTL_SECONDS = 1800
COUNTRIES_SAFE_MODE_SEED_TTL_SECONDS = 90
COUNTRIES_INDEX_QUOTE_TIMEOUT_SECONDS = 1.5
COUNTRIES_CONCURRENCY = 4
MARKET_MOVERS_TIMEOUT_SECONDS = 6
MARKET_MOVERS_WAIT_TIMEOUT_SECONDS = 2.5
MARKET_MOVERS_CACHE_TTL_SECONDS = 300
MARKET_INDICATORS_TIMEOUT_SECONDS = 5
MARKET_INDICATORS_WAIT_TIMEOUT_SECONDS = 2.0
MARKET_INDICATORS_CACHE_TTL_SECONDS = 300
HEATMAP_LAST_SUCCESS_TTL_SECONDS = 3600
MARKET_MOVERS_LAST_SUCCESS_TTL_SECONDS = 1800
MARKET_INDICATORS_LAST_SUCCESS_TTL_SECONDS = 1800
HEATMAP_TICKERS_PER_SECTOR = 2
HEATMAP_CHILDREN_PER_SECTOR = 2
HEATMAP_CONCURRENCY = 2
HEATMAP_WAIT_TIMEOUT_SECONDS = 2.5
MARKET_MOVERS_KR_REPRESENTATIVE_LIMIT = 60
COUNTRIES_CACHE_KEY = "countries:v2"
COUNTRIES_LAST_SUCCESS_KEY = "countries:last_success:v2"
PUBLIC_SIDE_EFFECT_SKIP_PRESSURE_RATIO = 0.84


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_sanitize_json_value(item) for item in value]
    return value


def _build_country_success_response(payload: dict) -> JSONResponse:
    encoded = jsonable_encoder(payload)
    return JSONResponse(status_code=200, content=_sanitize_json_value(encoded))


def _countries_payload_has_live_quotes(payload: Any) -> bool:
    if not isinstance(payload, list):
        return False
    for country in payload:
        if not isinstance(country, dict):
            continue
        for quote in country.get("indices") or []:
            if not isinstance(quote, dict):
                continue
            try:
                price = float(quote.get("price") or 0.0)
                change_pct = float(quote.get("change_pct") or 0.0)
            except (TypeError, ValueError):
                continue
            if abs(price) > 0 or abs(change_pct) > 0:
                return True
    return False


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


def _heatmap_has_tiles(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(isinstance(sector, dict) and sector.get("children") for sector in payload.get("children") or [])


def _market_movers_has_items(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("gainers") or payload.get("losers"))


def _market_indicators_have_values(payload: list[dict] | None) -> bool:
    if not isinstance(payload, list):
        return False
    return any(abs(float(item.get("price") or 0.0)) > 0.0001 for item in payload if isinstance(item, dict))


async def _load_cached_kr_representative_quotes(
    *,
    limit: int = MARKET_MOVERS_KR_REPRESENTATIVE_LIMIT,
    pages_per_market: int = 1,
) -> dict[str, dict]:
    from app.data import cache as data_cache

    session_token = market_session_cache_token(country_code="KR")
    cache_key = f"kr_market_quotes:representative:{max(1, int(pages_per_market))}:{session_token}"
    cached = await data_cache.get(cache_key)
    if not isinstance(cached, dict):
        return {}

    limited: dict[str, dict] = {}
    for ticker, quote in cached.items():
        if not isinstance(quote, dict):
            continue
        limited[ticker] = quote
        if len(limited) >= max(1, int(limit)):
            break
    return limited


def _build_heatmap_children_from_quotes(universe: dict[str, list[str]], quotes: dict[str, dict]) -> list[dict]:
    sectors: list[dict] = []
    for sector_name, tickers in universe.items():
        children: list[dict] = []
        for ticker in tickers:
            quote = quotes.get(ticker)
            if not isinstance(quote, dict):
                continue
            size = float(quote.get("market_cap") or quote.get("current_price") or 0.0)
            if size <= 0:
                continue
            children.append(
                {
                    "name": str(quote.get("ticker") or ticker).split(".")[0],
                    "ticker": quote.get("ticker") or ticker,
                    "fullName": quote.get("name") or ticker,
                    "size": round(size, 2),
                    "change": round(float(quote.get("change_pct") or 0.0), 2),
                }
            )
            if len(children) >= HEATMAP_CHILDREN_PER_SECTOR:
                break
        if children:
            children.sort(key=lambda item: float(item.get("size") or 0.0), reverse=True)
            sectors.append({"name": sector_name, "children": children})
    return sectors


async def _build_heatmap_fallback(code: str) -> dict:
    from app.data.universe_data import get_universe

    universe = await get_universe(code)
    if code == "KR":
        representative_quotes = await _load_cached_kr_representative_quotes()
        if not representative_quotes:
            try:
                representative_quotes = await asyncio.wait_for(
                    kr_market_quote_client.get_kr_representative_quotes(
                        limit=MARKET_MOVERS_KR_REPRESENTATIVE_LIMIT
                    ),
                    timeout=2.5,
                )
            except Exception as exc:
                logging.warning("heatmap representative fallback failed for %s: %s", code, exc)
                representative_quotes = {}

        sectors_from_quotes = _build_heatmap_children_from_quotes(universe, representative_quotes)
        if sectors_from_quotes:
            return {
                "children": sectors_from_quotes,
                "partial": True,
                "fallback_reason": "live_snapshot_timeout",
                "generated_at": datetime.now().isoformat(),
            }

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


def _record_market_opportunities_trace(
    started_at: float,
    *,
    request_phase: str,
    cache_state: str,
    payload: dict,
    served_state: str | None = None,
) -> None:
    timeout_budget_seconds = (
        OPPORTUNITY_TIMEOUT_SECONDS if request_phase == "full" else OPPORTUNITY_QUICK_TIMEOUT_SECONDS
    )
    route_stability_service.record_route_trace(
        "market_opportunities",
        build_route_trace(
            route_key="market_opportunities",
            request_phase=request_phase,
            cache_state=cache_state,
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            timeout_budget_ms=timeout_budget_seconds * 1000.0,
            upstream_source="market_service",
            payload=payload,
            served_state=served_state,
        ),
    )


def _build_traced_opportunity_partial(
    started_at: float,
    *,
    payload: dict,
    request_phase: str,
    cache_state: str,
    fallback_reason: str,
    note: str | None = None,
    fallback_tier: str | None = None,
    served_state: str | None = None,
) -> dict:
    response = _with_opportunity_partial(
        payload,
        fallback_reason=fallback_reason,
        note=note,
        fallback_tier=fallback_tier,
    )
    _record_market_opportunities_trace(
        started_at,
        request_phase=request_phase,
        cache_state=cache_state,
        payload=response,
        served_state=served_state,
    )
    return response


def _allow_public_background_refresh() -> bool:
    return not settings.startup_memory_safe_mode


def _country_report_refresh_retry_detail(code: str, *, background_enabled: bool) -> str:
    if background_enabled:
        return (
            f"{code} 국가 리포트 계산이 길어지고 있어 1차 보고서를 먼저 제공합니다. "
            "백그라운드 계산은 계속 진행되니 잠시 뒤 다시 열면 정밀 리포트가 바로 보일 수 있습니다."
        )
    return (
        f"{code} 국가 리포트 계산이 길어지고 있어 1차 보고서를 먼저 제공합니다. "
        "현재 응답에서는 무거운 후속 계산을 이어가지 않고, 다음 재조회에서 정밀 리포트를 다시 시도합니다."
    )


def _country_report_stale_detail(code: str) -> str:
    if _allow_public_background_refresh():
        return (
            f"{code} 국가 리포트 최신 계산은 백그라운드에서 계속 갱신하고 있으며, "
            "이번 응답에서는 최근 정상 리포트를 먼저 제공합니다."
        )
    return (
        f"{code} 국가 리포트 최신 계산은 이번 응답에서 안전한 경로로 보류하고, "
        "이번 응답에서는 최근 정상 리포트를 먼저 제공합니다. 다음 재조회에서 정밀 리포트를 다시 시도합니다."
    )


def _opportunity_refresh_followup_sentence() -> str:
    if _allow_public_background_refresh():
        return "정밀 후보 계산은 백그라운드에서 다시 시도합니다."
    return "정밀 후보 계산은 다음 재조회에서 다시 시도합니다."


def _maybe_trim_public_route_memory(reason: str) -> None:
    try:
        maybe_trim_process_memory(reason)
    except Exception as exc:
        logging.debug("memory trim skipped for %s: %s", reason, exc)


def _should_skip_public_side_effects() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    try:
        snapshot = get_memory_pressure_snapshot()
    except Exception as exc:
        logging.debug("country side effect memory snapshot failed: %s", exc)
        return False
    return float(snapshot.get("pressure_ratio") or 0.0) >= PUBLIC_SIDE_EFFECT_SKIP_PRESSURE_RATIO


async def _run_country_public_side_effect(
    job: Awaitable[Any],
    *,
    label: str,
    trim_reason: str,
) -> None:
    try:
        await job
    except asyncio.CancelledError:
        logging.warning("%s was cancelled before completion.", label)
    except Exception as exc:
        logging.warning("%s failed: %s", label, str(exc)[:180], exc_info=True)
    finally:
        _maybe_trim_public_route_memory(trim_reason)


def _spawn_country_public_side_effect(job: Awaitable[Any], *, label: str, trim_reason: str) -> bool:
    if _should_skip_public_side_effects():
        logging.info("Skipping %s because Render memory pressure is high.", label)
        _maybe_trim_public_route_memory(f"{trim_reason}:skip")
        return False
    asyncio.create_task(_run_country_public_side_effect(job, label=label, trim_reason=trim_reason))
    return True


def _schedule_country_report_persist(report: dict, code: str) -> bool:
    return _spawn_country_public_side_effect(
        archive_service.save_report("country", report, country_code=code),
        label=f"country report persist {code}",
        trim_reason="country_report_post",
    )


def _is_usable_opportunity_payload(payload: dict | None) -> bool:
    if not payload:
        return False
    return int(payload.get("quote_available_count") or 0) > 0 and bool(payload.get("opportunities"))


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


def _spawn_opportunity_refresh(code: str, limit: int) -> None:
    if not _allow_public_background_refresh():
        return
    code = code.upper()
    label = f"Opportunity radar background refresh for {code}"
    task, created = get_or_create_background_job(
        f"opportunity_refresh:{code}:{limit}",
        lambda: market_service.get_market_opportunities(code, limit),
    )
    if not created:
        logging.info("%s already running; reusing the existing refresh task.", label)
        return
    task.add_done_callback(
        lambda task_, refresh_label=label: _log_background_completion(task_, label=refresh_label)
    )


async def _capture_opportunity_payload(code: str, payload: dict) -> None:
    try:
        await prediction_capture_service.capture_market_opportunity_predictions(code, payload)
    except Exception as exc:
        logging.warning("opportunity prediction capture failed for %s: %s", code, exc, exc_info=True)


async def _build_countries_payload() -> list[dict]:
    index_requests: list[tuple[str, object, object]] = []
    for code, info in COUNTRY_REGISTRY.items():
        for idx in info.indices:
            index_requests.append((code, info, idx))

    async def _load_index_quote(entry: tuple[str, object, object]) -> dict:
        _code, _info, idx = entry
        try:
            quote = await asyncio.wait_for(
                yfinance_client.get_index_quote(idx.ticker),
                timeout=COUNTRIES_INDEX_QUOTE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logging.warning(
                "countries index quote timed out for %s after %.1fs",
                idx.ticker,
                COUNTRIES_INDEX_QUOTE_TIMEOUT_SECONDS,
            )
            quote = {"price": 0, "change_pct": 0}
        except Exception:
            SP_2005(idx.ticker).log()
            quote = {"price": 0, "change_pct": 0}
        return {
            "ticker": idx.ticker,
            "name": idx.name,
            "price": quote.get("price", 0),
            "change_pct": quote.get("change_pct", 0),
        }

    index_quotes = await gather_limited(
        index_requests,
        _load_index_quote,
        limit=COUNTRIES_CONCURRENCY,
    )

    quote_map: dict[str, list[dict]] = {code: [] for code in COUNTRY_REGISTRY}
    for request, quote in zip(index_requests, index_quotes):
        code = request[0]
        if isinstance(quote, Exception):
            idx = request[2]
            SP_2005(idx.ticker).log()
            quote = {"ticker": idx.ticker, "name": idx.name, "price": 0, "change_pct": 0}
        quote_map[code].append(quote)

    return [
        {
            "code": code,
            "name": info.name,
            "name_local": info.name_local,
            "currency": info.currency,
            "indices": quote_map.get(code, []),
        }
        for code, info in COUNTRY_REGISTRY.items()
    ]


def _build_countries_fallback() -> list[dict]:
    return [
        {
            "code": code,
            "name": info.name,
            "name_local": info.name_local,
            "currency": info.currency,
            "indices": [
                {
                    "ticker": idx.ticker,
                    "name": idx.name,
                    "price": 0,
                    "change_pct": 0,
                }
                for idx in info.indices
            ],
        }
        for code, info in COUNTRY_REGISTRY.items()
    ]


async def _fetch_countries_payload_for_cache() -> list[dict]:
    from app.data import cache as data_cache

    try:
        payload = await asyncio.wait_for(
            _build_countries_payload(),
            timeout=COUNTRIES_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logging.warning("countries payload timed out after %ss", COUNTRIES_TIMEOUT_SECONDS)
        payload = _build_countries_fallback()
    except Exception as exc:
        logging.warning("countries payload failed: %s", exc, exc_info=True)
        payload = _build_countries_fallback()

    if _countries_payload_has_live_quotes(payload):
        await data_cache.set(COUNTRIES_LAST_SUCCESS_KEY, payload, COUNTRIES_LAST_SUCCESS_TTL_SECONDS)
    return payload


async def _refresh_countries_cache_in_background() -> list[dict]:
    from app.data import cache as data_cache

    payload = await _fetch_countries_payload_for_cache()
    await data_cache.set(COUNTRIES_CACHE_KEY, payload, COUNTRIES_CACHE_TTL_SECONDS)
    _maybe_trim_public_route_memory("countries_refresh")
    return payload


def _spawn_countries_refresh() -> None:
    label = "Countries refresh"
    task, created = get_or_create_background_job(
        "countries_refresh:v2",
        _refresh_countries_cache_in_background,
    )
    if not created:
        logging.info("%s already running; reusing the existing refresh task.", label)
        return
    task.add_done_callback(
        lambda task_, refresh_label=label: _log_background_completion(task_, label=refresh_label)
    )


async def _build_market_movers_payload(code: str) -> dict:
    if code == "KR":
        representative_quotes = await kr_market_quote_client.get_kr_representative_quotes(
            limit=MARKET_MOVERS_KR_REPRESENTATIVE_LIMIT
        )
        if representative_quotes:
            stocks = [
                {
                    "ticker": quote.get("ticker") or ticker,
                    "name": quote.get("name") or ticker,
                    "price": round(float(quote.get("current_price") or 0.0), 2),
                    "change_pct": round(float(quote.get("change_pct") or 0.0), 2),
                }
                for ticker, quote in representative_quotes.items()
            ]
            stocks.sort(key=lambda item: item["change_pct"], reverse=True)
            return {
                "gainers": stocks[:5],
                "losers": list(reversed(stocks[-5:])) if len(stocks) >= 5 else list(reversed(stocks)),
            }

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
        stocks.append(
            {
                "ticker": item["ticker"],
                "name": item.get("name", item["ticker"]),
                "price": round(item.get("price", 0), 2),
                "change_pct": round(item.get("change_pct", 0), 2),
            }
        )

    stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    return {
        "gainers": stocks[:5],
        "losers": list(reversed(stocks[-5:])) if len(stocks) >= 5 else list(reversed(stocks)),
    }


def _build_market_movers_from_quotes(quotes: dict[str, dict]) -> dict:
    stocks = [
        {
            "ticker": quote.get("ticker") or ticker,
            "name": quote.get("name") or ticker,
            "price": round(float(quote.get("current_price") or quote.get("price") or 0.0), 2),
            "change_pct": round(float(quote.get("change_pct") or 0.0), 2),
        }
        for ticker, quote in quotes.items()
        if isinstance(quote, dict)
    ]
    stocks.sort(key=lambda item: item["change_pct"], reverse=True)
    return {
        "gainers": stocks[:5],
        "losers": list(reversed(stocks[-5:])) if len(stocks) >= 5 else list(reversed(stocks)),
    }


async def _build_market_movers_fallback(code: str, *, reason: str) -> dict:
    if code == "KR":
        representative_quotes = await _load_cached_kr_representative_quotes()
        if not representative_quotes:
            try:
                representative_quotes = await asyncio.wait_for(
                    kr_market_quote_client.get_kr_representative_quotes(
                        limit=MARKET_MOVERS_KR_REPRESENTATIVE_LIMIT
                    ),
                    timeout=2.5,
                )
            except Exception as exc:
                logging.warning("market movers representative fallback failed for %s: %s", code, exc)
                representative_quotes = {}
        if representative_quotes:
            payload = _build_market_movers_from_quotes(representative_quotes)
            payload["partial"] = True
            payload["fallback_reason"] = reason
            payload["generated_at"] = datetime.now().isoformat()
            return payload

    return {
        "gainers": [],
        "losers": [],
        "partial": True,
        "fallback_reason": reason,
        "generated_at": datetime.now().isoformat(),
    }


async def _build_market_indicators_payload() -> list[dict]:
    tickers = {
        "USD/KRW": "USDKRW=X",
        "Gold": "GC=F",
        "Oil (WTI)": "CL=F",
        "Bitcoin": "BTC-USD",
    }

    async def _load_indicator(item: tuple[str, str]) -> dict:
        name, ticker = item
        try:
            quote = await yfinance_client.get_index_quote(ticker)
        except Exception:
            quote = {"price": 0, "change_pct": 0}
        return {
            "name": name,
            "price": quote.get("price", 0),
            "change_pct": quote.get("change_pct", 0),
        }

    return await gather_limited(
        list(tickers.items()),
        _load_indicator,
        limit=len(tickers),
    )


def _build_market_indicators_fallback() -> list[dict]:
    return [
        {"name": "USD/KRW", "price": 0, "change_pct": 0},
        {"name": "Gold", "price": 0, "change_pct": 0},
        {"name": "Oil (WTI)", "price": 0, "change_pct": 0},
        {"name": "Bitcoin", "price": 0, "change_pct": 0},
    ]


async def _load_latest_archived_country_report(code: str) -> dict | None:
    try:
        archived_reports = await archive_service.list_reports("country", code, limit=1)
        if not archived_reports:
            return None
        latest = archived_reports[0]
        report_id = int(latest.get("id") or 0)
        if report_id <= 0:
            return None
        archived = await archive_service.get_report(report_id)
        payload = archived.get("report_json") if isinstance(archived, dict) else None
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        logging.warning("latest archived country report load failed for %s: %s", code, exc, exc_info=True)
        return None


async def _load_latest_cached_country_report(code: str) -> dict | None:
    from app.data import cache as data_cache

    payload = await data_cache.get(f"country_report:last_success:{code}")
    return payload if isinstance(payload, dict) else None


def _spawn_country_report_refresh(code: str) -> None:
    if not _allow_public_background_refresh():
        return
    label = f"Country report refresh for {code}"
    task, created = get_or_create_background_job(
        f"country_report:{code}",
        lambda: analyze_country(code),
    )
    if not created:
        logging.info("%s already running; reusing the existing refresh task.", label)
        return
    task.add_done_callback(
        lambda task_, refresh_label=label: _log_background_completion(task_, label=refresh_label)
    )


async def _build_country_report_fallback(
    code: str,
    *,
    reason: str,
    error_code: str | None,
    detail: str,
) -> dict:
    country = COUNTRY_REGISTRY[code]
    primary_index = country.indices[0]
    from app.data import cache as data_cache

    countries_snapshot = await data_cache.get("countries:v2")
    market_data = {}
    if isinstance(countries_snapshot, list):
        current = next((item for item in countries_snapshot if item.get("code") == code), None)
        if current:
            for idx, quote in zip(country.indices, current.get("indices", [])):
                market_data[idx.name] = {
                    "price": float(quote.get("price") or quote.get("current_price") or 0.0),
                    "change_pct": float(quote.get("change_pct") or 0.0),
                }
    if not market_data:
        market_data = {
            idx.name: {"price": 0.0, "change_pct": 0.0}
            for idx in country.indices
        }

    primary_price = float(
        market_data.get(primary_index.name, {}).get("price")
        or market_data.get(primary_index.name, {}).get("current_price")
        or 0.0
    )
    fear_greed = calculate_fear_greed([], country_code=code)
    forecast = {
        "index_ticker": primary_index.ticker,
        "index_name": primary_index.name,
        "current_price": primary_price,
        "fair_value": primary_price,
        "scenarios": [],
        "confidence_note": "정밀 분포 예측이 지연돼 대표 시장 스냅샷 기준 요약만 먼저 제공합니다.",
        "generated_at": datetime.now().isoformat(),
    }
    market_regime = {
        "label": f"{code} 기본 스냅샷",
        "stance": "neutral",
        "trend": "range",
        "volatility": "normal",
        "breadth": "mixed",
        "score": 50.0,
        "conviction": 38.0,
        "summary": "정밀 시장 국면 계산이 지연돼 대표 지수와 후보 스냅샷을 먼저 보여줍니다.",
        "playbook": [
            "대표 후보를 먼저 확인하고, 정밀 리포트가 회복되면 분포·기관 해석을 다시 확인합니다."
        ],
        "warnings": ["정밀 국가 리포트가 아직 준비되지 않았습니다."],
        "signals": [],
    }

    archived_report = await _load_latest_archived_country_report(code)
    quick_opportunities: list[dict] = []
    if not archived_report or not archived_report.get("top_stocks"):
        try:
            quick_response = await market_service.get_cached_market_opportunities(code, limit=5)
            if not _is_usable_opportunity_payload(quick_response):
                quick_response = await market_service.get_cached_market_opportunities_quick(code, limit=5)
            if not _is_usable_opportunity_payload(quick_response):
                quick_response = await asyncio.wait_for(
                    market_service.get_market_opportunities_quick(code, limit=5),
                    timeout=COUNTRY_REPORT_FALLBACK_OPPORTUNITY_TIMEOUT_SECONDS,
                )
            quick_opportunities = list(quick_response.get("opportunities") or [])
        except Exception as exc:
            logging.warning("country report fallback quick candidates failed for %s: %s", code, exc, exc_info=True)

    if archived_report:
        response = dict(archived_report)
        existing_summary = str(response.get("market_summary") or "").strip()
        fallback_lead = f"{country.name_local} 실시간 리포트 계산이 지연돼 최근 정상 리포트를 먼저 보여주고 있습니다."
        response["market_summary"] = " ".join(
            part for part in [fallback_lead, detail.strip(), existing_summary] if part
        ).strip()
        response["market_data"] = market_data or response.get("market_data") or {}
        if quick_opportunities and not response.get("top_stocks"):
            response["top_stocks"] = _build_top_stock_refs(quick_opportunities)
        errors = list(response.get("errors") or [])
        if error_code and error_code not in errors:
            errors.append(error_code)
        response["errors"] = errors
        response["llm_available"] = False
        response["partial"] = True
        response["fallback_reason"] = reason
        response["generated_at"] = datetime.now().isoformat()
        return response

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
        "forecast": forecast,
        "next_day_forecast": None,
        "market_regime": market_regime,
        "primary_index_history": [],
        "market_data": market_data,
        "llm_available": False,
        "errors": [error_code] if error_code else [],
        "partial": True,
        "fallback_reason": reason,
        "generated_at": datetime.now().isoformat(),
    }


async def _load_country_report_with_fallback(
    code: str,
    *,
    timeout_seconds: float,
    keep_background: bool,
    fallback_context: str = "public",
) -> tuple[dict, bool]:
    use_background_refresh = keep_background and _allow_public_background_refresh()
    if fallback_context == "export":
        timeout_detail = "내보내기용 정밀 리포트 생성이 길어져 1차 시장 스냅샷 기반 보고서를 대신 생성했습니다."
        error_detail = "내보내기용 정밀 리포트 생성 중 오류가 발생해 1차 시장 스냅샷 기반 보고서를 대신 생성했습니다."
        error_code = "SP-5004"
        log_label = "country report export load failed"
    else:
        timeout_detail = _country_report_refresh_retry_detail(
            code,
            background_enabled=use_background_refresh,
        )
        error_detail = "정밀 리포트 생성 중 오류가 발생해 1차 시장 스냅샷으로 우선 전환했습니다."
        error_code = "SP-3001"
        log_label = "country report load failed"

    if use_background_refresh:
        report_label = f"Country report for {code}"
        report_task, created = get_or_create_background_job(
            f"country_report:{code}",
            lambda: analyze_country(code),
        )
        if created:
            report_task.add_done_callback(
                lambda task, label=report_label: _log_background_completion(task, label=label)
            )
        try:
            report = await asyncio.wait_for(asyncio.shield(report_task), timeout=timeout_seconds)
            return report, False
        except asyncio.TimeoutError:
            return (
                await _build_country_report_fallback(
                    code,
                    reason="country_report_timeout",
                    error_code="SP-5018",
                    detail=timeout_detail,
                ),
                True,
            )
        except Exception as exc:
            logging.warning("country report failed for %s: %s", code, exc, exc_info=True)
            return (
                await _build_country_report_fallback(
                    code,
                    reason="country_report_error",
                    error_code=error_code,
                    detail=error_detail,
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
                detail=timeout_detail,
            ),
            True,
        )
    except Exception as exc:
        logging.warning("%s for %s: %s", log_label, code, exc, exc_info=True)
        return (
            await _build_country_report_fallback(
                code,
                reason="country_report_error",
                error_code=error_code,
                detail=error_detail,
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
    from app.data import cache as data_cache

    cached_response = await data_cache.get(COUNTRIES_CACHE_KEY)
    if isinstance(cached_response, list):
        _maybe_trim_public_route_memory("countries")
        return cached_response

    if settings.startup_memory_safe_mode:
        last_success = await data_cache.get(COUNTRIES_LAST_SUCCESS_KEY)
        _spawn_countries_refresh()
        if isinstance(last_success, list) and last_success:
            _maybe_trim_public_route_memory("countries")
            return last_success
        response = _build_countries_fallback()
        await data_cache.set(COUNTRIES_CACHE_KEY, response, COUNTRIES_SAFE_MODE_SEED_TTL_SECONDS)
        _maybe_trim_public_route_memory("countries")
        return response

    response = await data_cache.get_or_fetch(
        COUNTRIES_CACHE_KEY,
        _fetch_countries_payload_for_cache,
        ttl=COUNTRIES_CACHE_TTL_SECONDS,
        wait_timeout=COUNTRIES_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=_build_countries_fallback,
    )
    _maybe_trim_public_route_memory("countries")
    return response


@router.get("/country/{code}/report")
async def get_country_report(code: str):
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    cached_success = await _load_latest_cached_country_report(code)
    if cached_success:
        _spawn_country_report_refresh(code)
        _maybe_trim_public_route_memory("country_report")
        return _build_country_success_response(cached_success)

    archived_report = await _load_latest_archived_country_report(code)
    if archived_report:
        _spawn_country_report_refresh(code)
        report = await _build_country_report_fallback(
            code,
            reason="country_report_stale_public",
            error_code=None,
            detail=_country_report_stale_detail(code),
        )
        _maybe_trim_public_route_memory("country_report")
        return _build_country_success_response(report)

    try:
        report, partial = await _load_country_report_with_fallback(
            code,
            timeout_seconds=COUNTRY_REPORT_PUBLIC_TIMEOUT_SECONDS,
            keep_background=True,
            fallback_context="public",
        )
    except Exception as e:
        err = SP_3001(code)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    if not partial:
        _schedule_country_report_persist(report, code)

    _maybe_trim_public_route_memory("country_report")
    return _build_country_success_response(report)


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
    last_success_key = f"heatmap:last_success:{code}"

    async def _fetch_heatmap():
        try:
            payload = await asyncio.wait_for(_build_heatmap_payload(code), timeout=HEATMAP_TIMEOUT_SECONDS)
            if _heatmap_has_tiles(payload):
                await data_cache.set(last_success_key, payload, HEATMAP_LAST_SUCCESS_TTL_SECONDS)
            return payload
        except asyncio.TimeoutError:
            err = SP_5018(f"Heatmap for {code} exceeded {HEATMAP_TIMEOUT_SECONDS} seconds.")
            err.log("warning")
            cached_success = await data_cache.get(last_success_key)
            if _heatmap_has_tiles(cached_success):
                response = dict(cached_success)
                response["partial"] = True
                response["fallback_reason"] = "heatmap_last_success"
                response["generated_at"] = datetime.now().isoformat()
                return response
            return await _build_heatmap_fallback(code)
        except Exception as exc:
            logging.warning("heatmap failed for %s: %s", code, exc, exc_info=True)
            cached_success = await data_cache.get(last_success_key)
            if _heatmap_has_tiles(cached_success):
                response = dict(cached_success)
                response["partial"] = True
                response["fallback_reason"] = "heatmap_last_success"
                response["generated_at"] = datetime.now().isoformat()
                return response
            return await _build_heatmap_fallback(code)

    response = await data_cache.get_or_fetch(
        cache_key,
        _fetch_heatmap,
        ttl=900,
        wait_timeout=HEATMAP_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: _build_heatmap_fallback(code),
    )
    _maybe_trim_public_route_memory("country_heatmap")
    return response


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
            timeout_seconds=COUNTRY_REPORT_EXPORT_TIMEOUT_SECONDS,
            keep_background=False,
            fallback_context="export",
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
            timeout_seconds=COUNTRY_REPORT_EXPORT_TIMEOUT_SECONDS,
            keep_background=False,
            fallback_context="export",
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
    cache_key = "market_indicators:v2"
    last_success_key = "market_indicators:last_success"

    async def _fetch_indicators():
        try:
            payload = await asyncio.wait_for(
                _build_market_indicators_payload(),
                timeout=MARKET_INDICATORS_TIMEOUT_SECONDS,
            )
            if _market_indicators_have_values(payload):
                await data_cache.set(last_success_key, payload, MARKET_INDICATORS_LAST_SUCCESS_TTL_SECONDS)
            return payload
        except asyncio.TimeoutError:
            logging.warning("market indicators timed out after %ss", MARKET_INDICATORS_TIMEOUT_SECONDS)
            cached_success = await data_cache.get(last_success_key)
            if _market_indicators_have_values(cached_success):
                return cached_success
            return _build_market_indicators_fallback()
        except Exception as exc:
            logging.warning("market indicators failed: %s", exc, exc_info=True)
            cached_success = await data_cache.get(last_success_key)
            if _market_indicators_have_values(cached_success):
                return cached_success
            return _build_market_indicators_fallback()

    async def _timeout_indicator_fallback():
        cached_success = await data_cache.get(last_success_key)
        if _market_indicators_have_values(cached_success):
            return cached_success
        return _build_market_indicators_fallback()

    return await data_cache.get_or_fetch(
        cache_key,
        _fetch_indicators,
        ttl=MARKET_INDICATORS_CACHE_TTL_SECONDS,
        wait_timeout=MARKET_INDICATORS_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=_timeout_indicator_fallback,
    )


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

    return await data_cache.get_or_fetch(
        cache_key,
        _fetch_sector_performance,
        ttl=300,
        wait_timeout=COUNTRIES_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=list,
    )


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

    cache_key = f"movers:v2:{code}"
    last_success_key = f"movers:last_success:{code}"

    async def _fetch_movers():
        try:
            payload = await asyncio.wait_for(
                _build_market_movers_payload(code),
                timeout=MARKET_MOVERS_TIMEOUT_SECONDS,
            )
            payload["generated_at"] = datetime.now().isoformat()
            if _market_movers_has_items(payload):
                await data_cache.set(last_success_key, payload, MARKET_MOVERS_LAST_SUCCESS_TTL_SECONDS)
            return payload
        except asyncio.TimeoutError:
            logging.warning("market movers timed out for %s after %ss", code, MARKET_MOVERS_TIMEOUT_SECONDS)
            cached_success = await data_cache.get(last_success_key)
            if _market_movers_has_items(cached_success):
                response = dict(cached_success)
                response["partial"] = True
                response["fallback_reason"] = "market_movers_last_success"
                response["generated_at"] = datetime.now().isoformat()
                return response
            return await _build_market_movers_fallback(code, reason="market_movers_timeout")
        except Exception as exc:
            logging.warning("market movers failed for %s: %s", code, exc, exc_info=True)
            cached_success = await data_cache.get(last_success_key)
            if _market_movers_has_items(cached_success):
                response = dict(cached_success)
                response["partial"] = True
                response["fallback_reason"] = "market_movers_last_success"
                response["generated_at"] = datetime.now().isoformat()
                return response
            return await _build_market_movers_fallback(code, reason="market_movers_error")

    return await data_cache.get_or_fetch(
        cache_key,
        _fetch_movers,
        ttl=MARKET_MOVERS_CACHE_TTL_SECONDS,
        wait_timeout=MARKET_MOVERS_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: _build_market_movers_fallback(code, reason="market_movers_wait_timeout"),
    )


@router.get("/market/opportunities/{code}")
async def get_market_opportunities(code: str, limit: int = Query(12, ge=3, le=20)):
    started_at = time.perf_counter()
    code = code.upper()
    if code not in COUNTRY_REGISTRY:
        err = SP_6001(code)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    cached_full = await market_service.get_cached_market_opportunities(code, limit)
    if _is_usable_opportunity_payload(cached_full):
        await _capture_opportunity_payload(code, cached_full)
        _record_market_opportunities_trace(
            started_at,
            request_phase="full",
            cache_state="sqlite_hit",
            payload=cached_full,
        )
        _maybe_trim_public_route_memory("market_opportunities")
        return cached_full

    cached_quick = await market_service.get_cached_market_opportunities_quick(code, limit)
    if _is_usable_opportunity_payload(cached_quick):
        _spawn_opportunity_refresh(code, limit)
        await _capture_opportunity_payload(code, cached_quick)
        payload = _build_traced_opportunity_partial(
            started_at,
            payload=cached_quick,
            request_phase="quick",
            cache_state="sqlite_hit",
            fallback_reason="opportunity_cached_quick_response",
            note=(
                "이번 응답에서는 최근 usable 후보를 먼저 표시하고, "
                f"{_opportunity_refresh_followup_sentence()}"
            ),
            fallback_tier="cached_quick",
        )
        _maybe_trim_public_route_memory("market_opportunities")
        return payload

    quick_label = f"Opportunity quick fallback for {code}"
    quick_task = asyncio.create_task(market_service.get_market_opportunities_quick(code, limit))
    quick_task.add_done_callback(
        lambda task, label=quick_label: _log_background_completion(task, label=label)
    )
    try:
        quick_response = await asyncio.wait_for(
            quick_task,
            timeout=OPPORTUNITY_QUICK_TIMEOUT_SECONDS,
        )
        if _is_usable_opportunity_payload(quick_response):
            _spawn_opportunity_refresh(code, limit)
            await _capture_opportunity_payload(code, quick_response)
            payload = _build_traced_opportunity_partial(
                started_at,
                payload=quick_response,
                request_phase="quick",
                cache_state="miss",
                fallback_reason="opportunity_quick_response",
                note=(
                    "이번 응답에서는 1차 usable 후보를 먼저 표시하고, "
                    f"{_opportunity_refresh_followup_sentence()}"
                ),
            )
            _maybe_trim_public_route_memory("market_opportunities")
            return payload
    except asyncio.TimeoutError:
        logging.warning("opportunity quick fetch timed out for %s", code)
    except Exception as quick_exc:
        logging.warning("opportunity quick fetch failed for %s: %s", code, quick_exc, exc_info=True)

    cached_quick = await market_service.get_cached_market_opportunities_quick(code, limit)
    if _is_usable_opportunity_payload(cached_quick):
        _spawn_opportunity_refresh(code, limit)
        await _capture_opportunity_payload(code, cached_quick)
        payload = _build_traced_opportunity_partial(
            started_at,
            payload=cached_quick,
            request_phase="quick",
            cache_state="sqlite_hit",
            fallback_reason="opportunity_cached_quick_response",
            note=(
                "이번 응답에서는 최근 usable 후보를 먼저 표시하고, "
                f"{_opportunity_refresh_followup_sentence()}"
            ),
            fallback_tier="cached_quick",
        )
        _maybe_trim_public_route_memory("market_opportunities")
        return payload

    _spawn_opportunity_refresh(code, limit)
    payload = _build_traced_opportunity_partial(
        started_at,
        payload=market_service.build_market_opportunities_placeholder(
            code,
            note=(
                f"{code} 기회 레이더가 이번 요청에서 usable 후보를 만들지 못했습니다. "
                f"{_opportunity_refresh_followup_sentence()} "
                "다음 재조회에서는 quick 스냅샷과 캐시 재사용을 다시 확인합니다."
            ),
        ),
        request_phase="shell",
        cache_state="miss",
        fallback_reason="opportunity_placeholder_response",
        served_state="degraded",
    )
    _maybe_trim_public_route_memory("market_opportunities")
    return payload
