import asyncio
from collections.abc import Awaitable
from datetime import datetime, timezone
import logging
import math
import re
import sys
import time
from typing import Any

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.analysis.stock_cache_keys import stock_detail_latest_cache_key, stock_detail_quick_cache_key
from app.config import get_settings
from app.data import cache
from app.errors import SP_3003, SP_6003, SP_2005, SP_5002, SP_5010, SP_5014, SP_5018
from app.utils.lazy_module import LazyModuleProxy
from app.utils.memory_hygiene import get_memory_pressure_snapshot, maybe_trim_process_memory
from app.utils.route_trace import build_route_trace

router = APIRouter(prefix="/api", tags=["stock"])
logger = logging.getLogger(__name__)
settings = get_settings()
archive_service = LazyModuleProxy("app.services.archive_service")
forecast_monitor_service = LazyModuleProxy("app.services.forecast_monitor_service")
prediction_capture_service = LazyModuleProxy("app.services.prediction_capture_service")
route_stability_service = LazyModuleProxy("app.services.route_stability_service")
ticker_resolver_service = LazyModuleProxy("app.services.ticker_resolver_service")
yfinance_client = LazyModuleProxy("app.data.yfinance_client")
STOCK_DETAIL_TIMEOUT_SECONDS = 3.0
STOCK_DETAIL_PREFER_FULL_TIMEOUT_SECONDS = 14.0
STOCK_DETAIL_FULL_UPGRADE_GRACE_SECONDS = 1.5
STOCK_DETAIL_CACHE_LOOKUP_TIMEOUT_SECONDS = 0.35
STOCK_DETAIL_CACHE_WRITE_TIMEOUT_SECONDS = 0.25
STOCK_DISTRIBUTIONAL_CAPTURE_TIMEOUT_SECONDS = 0.2
_STOCK_DETAIL_REFRESH_TASKS: dict[str, asyncio.Task] = {}
_STOCK_DETAIL_QUICK_WARM_TASKS: dict[str, asyncio.Task] = {}
PUBLIC_SIDE_EFFECT_SKIP_PRESSURE_RATIO = 0.84
PUBLIC_FAST_FALLBACK_PRESSURE_RATIO = 0.8


async def analyze_stock(ticker: str) -> dict:
    from app.analysis.stock_analyzer import analyze_stock as _analyze_stock

    return await _analyze_stock(ticker)


async def build_quick_stock_detail(ticker: str) -> dict | None:
    from app.analysis.stock_analyzer import build_quick_stock_detail as _build_quick_stock_detail

    return await _build_quick_stock_detail(ticker)


async def get_cached_quick_stock_detail(ticker: str) -> dict | None:
    cached = await cache.get(stock_detail_quick_cache_key(ticker))
    return dict(cached) if cached else None


async def get_cached_stock_detail(ticker: str, *, refresh_quote: bool = False) -> dict | None:
    cached = await cache.get(stock_detail_latest_cache_key(ticker))
    if not cached:
        return None
    if not refresh_quote:
        return dict(cached)

    from app.analysis.stock_analyzer import get_cached_stock_detail as _get_cached_stock_detail

    return await _get_cached_stock_detail(ticker, refresh_quote=True)


def _maybe_trim_public_route_memory(reason: str) -> None:
    try:
        maybe_trim_process_memory(reason)
    except Exception:
        pass


async def _run_deferred_public_route_memory_trim(reason: str) -> None:
    await asyncio.to_thread(_maybe_trim_public_route_memory, reason)


def _schedule_public_route_memory_trim(reason: str | None) -> None:
    if not reason:
        return
    try:
        asyncio.create_task(_run_deferred_public_route_memory_trim(reason))
    except RuntimeError:
        _maybe_trim_public_route_memory(reason)


def _should_skip_public_side_effects() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    try:
        snapshot = get_memory_pressure_snapshot()
    except Exception:
        return False
    return float(snapshot.get("pressure_ratio") or 0.0) >= PUBLIC_SIDE_EFFECT_SKIP_PRESSURE_RATIO


def _public_memory_pressure_ratio() -> float:
    try:
        snapshot = get_memory_pressure_snapshot()
    except Exception:
        return 0.0
    return float(snapshot.get("pressure_ratio") or 0.0)


def _should_use_ultra_fast_public_fallback() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    return _public_memory_pressure_ratio() >= PUBLIC_FAST_FALLBACK_PRESSURE_RATIO


def _is_stock_analysis_module_warm() -> bool:
    return "app.analysis.stock_analyzer" in sys.modules


def _should_avoid_cold_stock_analysis_import() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    return not _is_stock_analysis_module_warm()


def _should_skip_public_stock_full_analysis() -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    return True


def _log_background_completion(task: asyncio.Task, *, label: str) -> None:
    if task.cancelled():
        logger.info("%s background task was cancelled.", label)
        return
    try:
        task.result()
    except Exception as exc:
        logger.warning("%s background task failed: %s", label, str(exc)[:180], exc_info=True)


def _cancel_background_task(task: asyncio.Task, *, label: str) -> None:
    if task.done():
        return
    task.cancel()
    logger.info("%s background task cancelled after fallback response.", label)


async def _run_stock_public_side_effect(
    job: Awaitable[Any],
    *,
    label: str,
    trim_reason: str,
) -> None:
    try:
        await job
    except asyncio.CancelledError:
        logger.warning("%s was cancelled before completion.", label)
    except Exception as exc:
        logger.warning("%s failed: %s", label, str(exc)[:180], exc_info=True)
    finally:
        _maybe_trim_public_route_memory(trim_reason)


def _spawn_stock_public_side_effect(job: Awaitable[Any], *, label: str, trim_reason: str) -> bool:
    if _should_skip_public_side_effects():
        logger.info("Skipping %s because Render memory pressure is high.", label)
        _maybe_trim_public_route_memory(f"{trim_reason}:skip")
        return False
    asyncio.create_task(_run_stock_public_side_effect(job, label=label, trim_reason=trim_reason))
    return True


def _schedule_stock_detail_persist(detail: dict, ticker: str) -> bool:
    return _spawn_stock_public_side_effect(
        _archive_stock_report(detail, ticker),
        label=f"stock detail persist {ticker}",
        trim_reason="stock_detail_post",
    )


def _consume_timeboxed_stock_task_result(task: asyncio.Task[Any]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        return


async def _run_timeboxed_stock_job(job: Awaitable[Any], *, timeout_seconds: float) -> tuple[Any | None, bool]:
    task = asyncio.ensure_future(job)
    task.add_done_callback(_consume_timeboxed_stock_task_result)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), timeout=max(timeout_seconds, 0.01))
        return result, False
    except asyncio.TimeoutError:
        task.cancel()
        return None, True


async def _timed_stock_cache_lookup(job: Awaitable[Any], *, label: str) -> Any | None:
    try:
        result, timed_out = await _run_timeboxed_stock_job(
            job,
            timeout_seconds=STOCK_DETAIL_CACHE_LOOKUP_TIMEOUT_SECONDS,
        )
        if not timed_out:
            return result
        logger.warning("%s timed out after %.2fs; continuing as cache miss.", label, STOCK_DETAIL_CACHE_LOOKUP_TIMEOUT_SECONDS)
        return None
    except Exception as exc:
        logger.warning("%s failed: %s", label, str(exc)[:180], exc_info=True)
        return None


async def _timed_stock_cache_write(job: Awaitable[Any], *, label: str) -> bool:
    try:
        _, timed_out = await _run_timeboxed_stock_job(
            job,
            timeout_seconds=STOCK_DETAIL_CACHE_WRITE_TIMEOUT_SECONDS,
        )
        if not timed_out:
            return True
        logger.warning(
            "%s timed out after %.2fs; continuing without blocking the response.",
            label,
            STOCK_DETAIL_CACHE_WRITE_TIMEOUT_SECONDS,
        )
        return False
    except Exception as exc:
        logger.warning("%s failed: %s", label, str(exc)[:180], exc_info=True)
        return False


def _record_stock_detail_trace(
    started_at: float,
    *,
    request_phase: str,
    cache_state: str,
    timeout_budget_seconds: float | None,
    payload: dict | None = None,
    fallback_reason: str | None = None,
    served_state: str | None = None,
) -> None:
    route_stability_service.record_route_trace(
        "stock_detail",
        build_route_trace(
            route_key="stock_detail",
            request_phase=request_phase,
            cache_state=cache_state,
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            timeout_budget_ms=(timeout_budget_seconds * 1000.0) if timeout_budget_seconds else None,
            upstream_source="yahoo_finance",
            payload=payload,
            fallback_reason=fallback_reason,
            served_state=served_state,
        ),
    )


def _resolve_kr_ticker(ticker: str, *, allow_fast_path: bool = False) -> str:
    normalized = str(ticker or "").strip().replace(" ", "").upper()
    if not normalized:
        return ""
    if allow_fast_path:
        if normalized.endswith((".KS", ".KQ", ".KR")):
            return normalized
        if re.fullmatch(r"\d{6}", normalized):
            return f"{normalized}.KS"
    return ticker_resolver_service.resolve_ticker(normalized, "KR")["ticker"] or normalized


def _build_partial_stock_detail(cached: dict, *, error_code: str | None, fallback_reason: str) -> dict:
    partial = dict(cached)
    errors = list(partial.get("errors") or [])
    if error_code and error_code not in errors:
        errors.append(error_code)
    partial["errors"] = errors
    partial["partial"] = True
    partial["fallback_reason"] = fallback_reason
    partial["generated_at"] = partial.get("generated_at") or datetime.now(timezone.utc).isoformat()
    return partial


def _blank_score_detail(max_score: float = 20.0) -> dict:
    return {
        "total": 0.0,
        "max_score": max_score,
        "items": [],
    }


def _blank_stock_score() -> dict:
    return {
        "total": 0.0,
        "fundamental": _blank_score_detail(),
        "valuation": _blank_score_detail(),
        "growth_momentum": _blank_score_detail(),
        "analyst": _blank_score_detail(),
        "risk": _blank_score_detail(),
    }


def _blank_composite_score() -> dict:
    return {
        "total": 0.0,
        "total_raw": 0.0,
        "max_raw": 100.0,
        "fundamental": _blank_score_detail(),
        "valuation": _blank_score_detail(),
        "growth_momentum": _blank_score_detail(),
        "analyst": _blank_score_detail(),
        "risk": _blank_score_detail(),
        "technical": _blank_score_detail(),
    }


def _blank_technical_indicators() -> dict:
    return {
        "ma_20": [],
        "ma_60": [],
        "rsi_14": [],
        "macd": [],
        "macd_signal": [],
        "macd_hist": [],
        "dates": [],
    }


async def _build_stock_memory_guard_shell(ticker: str) -> dict:
    metadata = ticker_resolver_service.get_ticker_metadata(ticker)
    current_price = 0.0
    fallback_summary = (
        "현재 서버 메모리 보호 구간이라 정밀 종목 분석 대신 최소 상세 스냅샷을 먼저 제공합니다. "
        "외부 가격 조회도 이번 응답에서는 건너뛰며, 잠시 뒤 다시 조회하면 quick 또는 full 캐시 결과가 보일 수 있습니다."
    )
    payload = {
        "ticker": ticker,
        "name": ticker,
        "country_code": metadata.get("country_code") or "KR",
        "sector": metadata.get("sector") or "Unknown",
        "industry": "N/A",
        "market_cap": 0.0,
        "current_price": current_price,
        "change_pct": 0.0,
        "financials": [],
        "pe_ratio": None,
        "pb_ratio": None,
        "ev_ebitda": None,
        "peg_ratio": None,
        "week52_high": None,
        "week52_low": None,
        "peer_comparisons": [],
        "dividend": {
            "dividend_yield": None,
            "payout_ratio": None,
            "dividend_growth_5y": None,
        },
        "analyst_ratings": {
            "buy": 0,
            "hold": 0,
            "sell": 0,
            "target_mean": None,
            "target_median": None,
            "target_high": None,
            "target_low": None,
        },
        "earnings_history": [],
        "price_history": [],
        "technical": _blank_technical_indicators(),
        "score": _blank_stock_score(),
        "composite_score": _blank_composite_score(),
        "buy_sell_guide": {
            "buy_zone_low": current_price,
            "buy_zone_high": current_price,
            "fair_value": current_price,
            "sell_zone_low": current_price,
            "sell_zone_high": current_price,
            "risk_reward_ratio": 0.0,
            "confidence_grade": "대기",
            "methodology": [],
            "summary": "정밀 매매 가이드는 이번 응답에서 생략했습니다.",
        },
        "next_day_forecast": None,
        "free_kr_forecast": None,
        "historical_pattern_forecast": None,
        "setup_backtest": None,
        "market_regime": {
            "label": "KR 기본 스냅샷",
            "stance": "neutral",
            "trend": "range",
            "volatility": "normal",
            "breadth": "mixed",
            "score": 48.0,
            "conviction": 28.0,
            "summary": "메모리 보호 구간이라 시장 국면은 기본 스냅샷으로 유지합니다.",
            "playbook": ["현재 응답은 최소 상세 스냅샷입니다. 잠시 뒤 다시 조회해 정밀 지표를 확인합니다."],
            "warnings": ["정밀 종목 분석이 이번 요청에서는 보류되었습니다."],
            "signals": [],
        },
        "trade_plan": {
            "setup_label": "대기",
            "action": "wait_pullback",
            "conviction": 24.0,
            "entry_low": current_price or None,
            "entry_high": current_price or None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "expected_holding_days": 5,
            "risk_reward_estimate": 0.0,
            "thesis": ["정밀 종목 분석을 기다리는 동안 최소 시세 스냅샷만 제공합니다."],
            "invalidation": "정밀 종목 분석이 다시 가능해지면 계획을 갱신합니다.",
        },
        "public_summary": {
            "summary": fallback_summary,
            "evidence_for": [],
            "evidence_against": [],
            "why_not_buy_now": ["현재 응답은 메모리 보호 모드에서 생성된 최소 스냅샷입니다."],
            "thesis_breakers": ["정밀 분석이 회복되기 전에는 이 요약만으로 매수 결정을 내리기 어렵습니다."],
            "data_quality": "티커·기본 메타데이터 중심 최소 응답",
            "confidence_note": "정밀 예측과 기술 지표 계산은 이번 요청에서 생략했습니다.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "partial": True,
        "fallback_reason": "stock_memory_guard",
        "llm_available": False,
        "errors": [],
        "analysis_summary": fallback_summary,
        "key_risks": ["서버 메모리 보호 구간이라 이번 요청에서는 정밀 종목 분석을 이어가지 않았습니다."],
        "key_catalysts": [],
    }
    await _timed_stock_cache_write(
        cache.set(
            f"stock_detail:quick-v1:{ticker}",
            payload,
            ttl=min(get_settings().cache_ttl_report, 120),
            persist=False,
        ),
        label=f"stock guard-shell cache write {ticker}",
    )
    return payload


async def _build_stock_minimal_shell(
    ticker: str,
    *,
    fallback_reason: str,
    summary: str,
    error_code: str | None = None,
) -> dict:
    payload = await _build_stock_memory_guard_shell(ticker)
    payload["fallback_reason"] = fallback_reason
    payload["analysis_summary"] = summary
    payload["key_risks"] = [summary]
    payload["trade_plan"] = {
        **dict(payload.get("trade_plan") or {}),
        "thesis": [summary],
        "invalidation": "정밀 종목 분석이 다시 가능해지면 계획을 갱신합니다.",
    }
    payload["public_summary"] = {
        **dict(payload.get("public_summary") or {}),
        "summary": summary,
        "why_not_buy_now": [summary],
        "thesis_breakers": [
            "정밀 종목 분석이 회복될 때까지 최소 스냅샷만으로는 판단 근거가 충분하지 않습니다."
        ],
        "data_quality": "티커·기본 메타데이터 중심 최소 응답",
        "confidence_note": "정밀 예측과 기술 지표 계산은 이번 요청에서 생략했습니다.",
    }
    errors = list(payload.get("errors") or [])
    if error_code and error_code not in errors:
        errors.append(error_code)
    payload["errors"] = errors
    return payload


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


def _build_stock_success_response(payload: dict, *, trim_reason: str | None = None) -> JSONResponse:
    encoded = jsonable_encoder(payload)
    response = JSONResponse(status_code=200, content=_sanitize_json_value(encoded))
    _schedule_public_route_memory_trim(trim_reason)
    return response


def _build_stock_error_response(status_code: int, content: dict, *, trim_reason: str | None = None) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content=content)
    _schedule_public_route_memory_trim(trim_reason)
    return response


def _stock_detail_upgrade_timeout_seconds() -> float:
    return min(STOCK_DETAIL_FULL_UPGRADE_GRACE_SECONDS, STOCK_DETAIL_PREFER_FULL_TIMEOUT_SECONDS)


async def _run_timed_stock_analysis(ticker: str, *, timeout_seconds: float, label: str) -> dict:
    analysis_task = asyncio.create_task(analyze_stock(ticker))
    analysis_task.add_done_callback(
        lambda task, task_label=label: _log_background_completion(task, label=task_label)
    )
    try:
        return await asyncio.wait_for(asyncio.shield(analysis_task), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        _cancel_background_task(analysis_task, label=label)
        raise
    except Exception:
        _cancel_background_task(analysis_task, label=label)
        raise


async def _try_schedule_distributional_capture(ticker: str) -> bool:
    if bool(getattr(settings, "startup_memory_safe_mode", False)):
        logger.info(
            "Skipping stock distributional capture for %s because Render safe mode keeps public stock detail side effects off.",
            ticker,
        )
        return False
    if _should_skip_public_side_effects():
        logger.info("Skipping stock distributional capture for %s because Render memory pressure is high.", ticker)
        return False
    try:
        return await asyncio.wait_for(
            prediction_capture_service.schedule_stock_distributional_capture(ticker),
            timeout=STOCK_DISTRIBUTIONAL_CAPTURE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "stock distributional capture scheduling timed out for %s after %.2fs",
            ticker,
            STOCK_DISTRIBUTIONAL_CAPTURE_TIMEOUT_SECONDS,
        )
        return False
    except Exception as exc:
        logger.warning("stock distributional capture scheduling failed for %s: %s", ticker, str(exc)[:180], exc_info=True)
        return False


def _build_traced_partial_stock_detail(
    started_at: float,
    *,
    cached: dict,
    cache_state: str,
    timeout_budget_seconds: float,
    error_code: str | None,
    fallback_reason: str,
    served_state: str | None = None,
) -> dict:
    partial_payload = _build_partial_stock_detail(
        cached,
        error_code=error_code,
        fallback_reason=fallback_reason,
    )
    _record_stock_detail_trace(
        started_at,
        request_phase="quick" if fallback_reason == "stock_quick_detail" else "full",
        cache_state=cache_state,
        timeout_budget_seconds=timeout_budget_seconds,
        payload=partial_payload,
        served_state=served_state,
    )
    return partial_payload


async def _finalize_stock_detail_response(detail: dict, ticker: str, *, prefer_full: bool, cache_state: str) -> JSONResponse:
    _schedule_stock_detail_persist(detail, ticker)

    logger.info(
        "stock detail served | ticker=%s request_phase=full cache_state=%s served_state=fresh prefer_full=%s",
        ticker,
        cache_state,
        prefer_full,
    )
    return _build_stock_success_response(detail, trim_reason="stock_detail")


async def _archive_stock_report(detail: dict, ticker: str) -> None:
    try:
        await archive_service.save_report("stock", detail, ticker=ticker)
    except Exception as exc:
        SP_5002(str(exc)[:100]).log()


def _schedule_stock_detail_refresh(ticker: str) -> bool:
    if not settings.effective_stock_detail_background_refresh:
        return False
    if bool(getattr(settings, "startup_memory_safe_mode", False)):
        logger.info(
            "Skipping stock detail background refresh for %s because Render safe mode keeps public stock detail on the quick-only path.",
            ticker,
        )
        return False
    if _should_avoid_cold_stock_analysis_import():
        logger.info(
            "Skipping stock detail background refresh for %s because Render safe mode avoids cold stock analysis import.",
            ticker,
        )
        return False
    if _should_skip_public_stock_full_analysis():
        logger.info(
            "Skipping stock detail background refresh for %s because Render memory pressure is elevated.",
            ticker,
        )
        return False

    existing = _STOCK_DETAIL_REFRESH_TASKS.get(ticker)
    if existing and not existing.done():
        return True

    async def _run_refresh() -> None:
        try:
            detail = await analyze_stock(ticker)
            await _archive_stock_report(detail, ticker)
        except Exception as exc:
            logger.warning("stock detail background refresh failed for %s: %s", ticker, str(exc)[:180])
        finally:
            _STOCK_DETAIL_REFRESH_TASKS.pop(ticker, None)

    _STOCK_DETAIL_REFRESH_TASKS[ticker] = asyncio.create_task(_run_refresh())
    return True


def _schedule_stock_detail_quick_warm(ticker: str) -> bool:
    if not bool(getattr(settings, "startup_memory_safe_mode", False)):
        return False
    if _should_skip_public_side_effects():
        logger.info(
            "Skipping stock detail quick warm for %s because Render memory pressure is high.",
            ticker,
        )
        return False
    if not _is_stock_analysis_module_warm():
        logger.info(
            "Skipping stock detail quick warm for %s because stock analysis module is still cold.",
            ticker,
        )
        return False

    existing = _STOCK_DETAIL_QUICK_WARM_TASKS.get(ticker)
    if existing and not existing.done():
        return True

    async def _run_quick_warm() -> None:
        try:
            await asyncio.wait_for(build_quick_stock_detail(ticker), timeout=STOCK_DETAIL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "stock detail quick warm timed out for %s after %.2fs",
                ticker,
                STOCK_DETAIL_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "stock detail quick warm failed for %s: %s",
                ticker,
                str(exc)[:180],
                exc_info=True,
            )
        finally:
            _STOCK_DETAIL_QUICK_WARM_TASKS.pop(ticker, None)
            _maybe_trim_public_route_memory("stock_detail_quick_warm_post")

    _STOCK_DETAIL_QUICK_WARM_TASKS[ticker] = asyncio.create_task(_run_quick_warm())
    return True


async def _serve_quick_stock_detail(
    started_at: float,
    *,
    ticker: str,
    prefer_full: bool,
    quick_snapshot: dict,
    cache_state: str,
    source_label: str,
) -> JSONResponse:
    if prefer_full:
        if _should_skip_public_stock_full_analysis():
            await _try_schedule_distributional_capture(ticker)
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=quick_snapshot,
                cache_state=cache_state,
                timeout_budget_seconds=_stock_detail_upgrade_timeout_seconds(),
                error_code=None,
                fallback_reason="stock_memory_guard",
            )
            logger.info(
                "stock detail served | ticker=%s request_phase=quick cache_state=%s served_state=partial prefer_full=%s fallback_reason=stock_memory_guard",
                ticker,
                cache_state,
                prefer_full,
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        upgrade_timeout = _stock_detail_upgrade_timeout_seconds()
        try:
            detail = await _run_timed_stock_analysis(
                ticker,
                timeout_seconds=upgrade_timeout,
                label=f"stock prefer-full analyze {ticker}",
            )
            _record_stock_detail_trace(
                started_at,
                request_phase="full",
                cache_state=cache_state,
                timeout_budget_seconds=upgrade_timeout,
                payload=detail,
            )
            return await _finalize_stock_detail_response(
                detail,
                ticker,
                prefer_full=prefer_full,
                cache_state=cache_state,
            )
        except asyncio.TimeoutError:
            await _try_schedule_distributional_capture(ticker)
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=quick_snapshot,
                cache_state=cache_state,
                timeout_budget_seconds=upgrade_timeout,
                error_code="SP-5018",
                fallback_reason="stock_quick_detail",
            )
            logger.info(
                "stock detail served | ticker=%s request_phase=quick cache_state=%s served_state=partial prefer_full=%s fallback_reason=stock_quick_detail",
                ticker,
                cache_state,
                prefer_full,
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        except Exception as exc:
            await _try_schedule_distributional_capture(ticker)
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=quick_snapshot,
                cache_state=cache_state,
                timeout_budget_seconds=upgrade_timeout,
                error_code="SP-3003",
                fallback_reason="stock_quick_detail",
            )
            logger.warning(
                "stock detail degraded to %s after full upgrade failure | ticker=%s prefer_full=%s detail=%s",
                source_label,
                ticker,
                prefer_full,
                str(exc)[:200],
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")

    _schedule_stock_detail_refresh(ticker)
    await _try_schedule_distributional_capture(ticker)
    partial_payload = _build_traced_partial_stock_detail(
        started_at,
        cached=quick_snapshot,
        cache_state=cache_state,
        timeout_budget_seconds=STOCK_DETAIL_TIMEOUT_SECONDS,
        error_code=None,
        fallback_reason="stock_quick_detail",
    )
    logger.info(
        "stock detail served | ticker=%s request_phase=quick cache_state=%s served_state=partial prefer_full=%s",
        ticker,
        cache_state,
        prefer_full,
    )
    return _build_stock_success_response(partial_payload, trim_reason="stock_detail")


@router.get("/stock/{ticker}/detail")
async def get_stock_detail(
    ticker: str,
    prefer_full: bool = Query(default=False, description="partial snapshot 이후 full detail 업그레이드를 우선 시도합니다."),
):
    started_at = time.perf_counter()
    detail_timeout = STOCK_DETAIL_PREFER_FULL_TIMEOUT_SECONDS if prefer_full else STOCK_DETAIL_TIMEOUT_SECONDS
    if not prefer_full and (_should_use_ultra_fast_public_fallback() or _should_avoid_cold_stock_analysis_import()):
        ticker = _resolve_kr_ticker(ticker, allow_fast_path=True)
        shell_payload = await _build_stock_memory_guard_shell(ticker)
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="skipped",
            timeout_budget_seconds=detail_timeout,
            payload=shell_payload,
            fallback_reason="stock_memory_guard",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
    ticker = _resolve_kr_ticker(ticker)
    cached = await _timed_stock_cache_lookup(
        get_cached_stock_detail(ticker, refresh_quote=False),
        label=f"stock full cache lookup {ticker}",
    )
    if cached:
        _record_stock_detail_trace(
            started_at,
            request_phase="full",
            cache_state="sqlite_hit",
            timeout_budget_seconds=STOCK_DETAIL_PREFER_FULL_TIMEOUT_SECONDS if prefer_full else STOCK_DETAIL_TIMEOUT_SECONDS,
            payload=cached,
        )
        logger.info(
            "stock detail served | ticker=%s request_phase=full cache_state=sqlite_hit served_state=fresh prefer_full=%s",
            ticker,
            prefer_full,
        )
        return _build_stock_success_response(cached, trim_reason="stock_detail")

    cached_quick = await _timed_stock_cache_lookup(
        get_cached_quick_stock_detail(ticker),
        label=f"stock quick cache lookup {ticker}",
    )
    quick_fallback = cached_quick
    if cached_quick:
        if prefer_full and _should_use_ultra_fast_public_fallback():
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=cached_quick,
                cache_state="sqlite_hit",
                timeout_budget_seconds=detail_timeout,
                error_code=None,
                fallback_reason="stock_memory_guard",
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        return await _serve_quick_stock_detail(
            started_at,
            ticker=ticker,
            prefer_full=prefer_full,
            quick_snapshot=cached_quick,
            cache_state="sqlite_hit",
            source_label="cached quick snapshot",
        )

    if _should_use_ultra_fast_public_fallback():
        shell_payload = await _build_stock_memory_guard_shell(ticker)
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="miss",
            timeout_budget_seconds=detail_timeout,
            payload=shell_payload,
            fallback_reason="stock_memory_guard",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
    if _should_avoid_cold_stock_analysis_import():
        logger.info(
            "Serving stock memory guard shell for %s because Render safe mode avoids cold stock analysis import.",
            ticker,
        )
        shell_payload = await _build_stock_memory_guard_shell(ticker)
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="miss",
            timeout_budget_seconds=detail_timeout,
            payload=shell_payload,
            fallback_reason="stock_memory_guard",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
    if bool(getattr(settings, "startup_memory_safe_mode", False)) and not prefer_full:
        _schedule_stock_detail_quick_warm(ticker)
        logger.info(
            "Serving stock memory guard shell for %s while quick snapshot warm-up runs in the background.",
            ticker,
        )
        shell_payload = await _build_stock_memory_guard_shell(ticker)
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="miss",
            timeout_budget_seconds=detail_timeout,
            payload=shell_payload,
            fallback_reason="stock_memory_guard",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")

    try:
        if quick_fallback is None:
            quick_fallback = await asyncio.wait_for(
                build_quick_stock_detail(ticker),
                timeout=STOCK_DETAIL_TIMEOUT_SECONDS,
            )
        if quick_fallback:
            return await _serve_quick_stock_detail(
                started_at,
                ticker=ticker,
                prefer_full=prefer_full,
                quick_snapshot=quick_fallback,
                cache_state="miss",
                source_label="fresh quick snapshot",
            )
        if _should_skip_public_stock_full_analysis():
            shell_payload = await _build_stock_memory_guard_shell(ticker)
            _record_stock_detail_trace(
                started_at,
                request_phase="shell",
                cache_state="miss",
                timeout_budget_seconds=detail_timeout,
                payload=shell_payload,
                fallback_reason="stock_memory_guard",
                served_state="degraded",
            )
            return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
        detail = await _run_timed_stock_analysis(
            ticker,
            timeout_seconds=detail_timeout,
            label=f"stock detail analyze {ticker}",
        )
    except asyncio.TimeoutError:
        cached_quick = quick_fallback or await _timed_stock_cache_lookup(
            get_cached_quick_stock_detail(ticker),
            label=f"stock quick cache lookup after timeout {ticker}",
        )
        if cached_quick:
            if not prefer_full:
                _schedule_stock_detail_refresh(ticker)
            await _try_schedule_distributional_capture(ticker)
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=cached_quick,
                cache_state="sqlite_hit",
                timeout_budget_seconds=detail_timeout,
                error_code="SP-5018",
                fallback_reason="stock_quick_detail",
            )
            logger.info(
                "stock detail served | ticker=%s request_phase=quick cache_state=sqlite_hit served_state=partial prefer_full=%s fallback_reason=stock_quick_detail",
                ticker,
                prefer_full,
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        cached = await _timed_stock_cache_lookup(
            get_cached_stock_detail(ticker, refresh_quote=False),
            label=f"stock full cache lookup after timeout {ticker}",
        )
        if cached:
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=cached,
                cache_state="sqlite_hit",
                timeout_budget_seconds=detail_timeout,
                error_code="SP-5018",
                fallback_reason="stock_cached_detail",
                served_state="stale",
            )
            logger.info(
                "stock detail served | ticker=%s request_phase=full cache_state=sqlite_hit served_state=stale prefer_full=%s fallback_reason=stock_cached_detail",
                ticker,
                prefer_full,
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        err = SP_5018(f"Stock detail timed out for {ticker}")
        err.log()
        if _should_use_ultra_fast_public_fallback():
            shell_payload = await _build_stock_memory_guard_shell(ticker)
            _record_stock_detail_trace(
                started_at,
                request_phase="shell",
                cache_state="miss",
                timeout_budget_seconds=detail_timeout,
                payload=shell_payload,
                fallback_reason="stock_memory_guard",
                served_state="degraded",
            )
            return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
        shell_payload = await _build_stock_minimal_shell(
            ticker,
            fallback_reason="stock_minimal_shell",
            summary=(
                "상세 종목 분석이 지연돼 이번 요청에서는 최소 상세 스냅샷을 먼저 제공합니다. "
                "잠시 뒤 다시 조회하면 quick 또는 full 캐시 결과가 보일 수 있습니다."
            ),
            error_code="SP-5018",
        )
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="miss",
            timeout_budget_seconds=detail_timeout,
            payload=shell_payload,
            fallback_reason="stock_minimal_shell",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
    except Exception as e:
        cached_quick = quick_fallback or await _timed_stock_cache_lookup(
            get_cached_quick_stock_detail(ticker),
            label=f"stock quick cache lookup after error {ticker}",
        )
        if cached_quick:
            if not prefer_full:
                _schedule_stock_detail_refresh(ticker)
            await _try_schedule_distributional_capture(ticker)
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=cached_quick,
                cache_state="sqlite_hit" if quick_fallback is None else "miss",
                timeout_budget_seconds=detail_timeout if "detail_timeout" in locals() else STOCK_DETAIL_TIMEOUT_SECONDS,
                error_code="SP-3003",
                fallback_reason="stock_quick_detail",
            )
            logger.warning(
                "stock detail degraded to quick snapshot | ticker=%s prefer_full=%s detail=%s",
                ticker,
                prefer_full,
                str(e)[:200],
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        cached = await _timed_stock_cache_lookup(
            get_cached_stock_detail(ticker, refresh_quote=False),
            label=f"stock full cache lookup after error {ticker}",
        )
        if cached:
            partial_payload = _build_traced_partial_stock_detail(
                started_at,
                cached=cached,
                cache_state="sqlite_hit",
                timeout_budget_seconds=detail_timeout if "detail_timeout" in locals() else STOCK_DETAIL_TIMEOUT_SECONDS,
                error_code="SP-3003",
                fallback_reason="stock_cached_detail",
                served_state="stale",
            )
            logger.warning(
                "stock detail degraded to cached full snapshot | ticker=%s prefer_full=%s detail=%s",
                ticker,
                prefer_full,
                str(e)[:200],
            )
            return _build_stock_success_response(partial_payload, trim_reason="stock_detail")
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        if _should_use_ultra_fast_public_fallback():
            shell_payload = await _build_stock_memory_guard_shell(ticker)
            _record_stock_detail_trace(
                started_at,
                request_phase="shell",
                cache_state="miss",
                timeout_budget_seconds=detail_timeout if "detail_timeout" in locals() else STOCK_DETAIL_TIMEOUT_SECONDS,
                payload=shell_payload,
                fallback_reason="stock_memory_guard",
                served_state="degraded",
            )
            return _build_stock_success_response(shell_payload, trim_reason="stock_detail")
        shell_payload = await _build_stock_minimal_shell(
            ticker,
            fallback_reason="stock_minimal_shell",
            summary=(
                "상세 종목 분석을 완료하지 못해 이번 요청에서는 최소 상세 스냅샷을 먼저 제공합니다. "
                "잠시 뒤 다시 조회하면 quick 또는 full 캐시 결과가 보일 수 있습니다."
            ),
            error_code="SP-3003",
        )
        _record_stock_detail_trace(
            started_at,
            request_phase="shell",
            cache_state="miss",
            timeout_budget_seconds=detail_timeout if "detail_timeout" in locals() else STOCK_DETAIL_TIMEOUT_SECONDS,
            payload=shell_payload,
            fallback_reason="stock_minimal_shell",
            served_state="degraded",
        )
        return _build_stock_success_response(shell_payload, trim_reason="stock_detail")

    _record_stock_detail_trace(
        started_at,
        request_phase="full",
        cache_state="miss",
        timeout_budget_seconds=detail_timeout,
        payload=detail,
    )
    return await _finalize_stock_detail_response(
        detail,
        ticker,
        prefer_full=prefer_full,
        cache_state="miss",
    )


@router.get("/stock/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "3mo"):
    ticker = _resolve_kr_ticker(ticker)
    allowed = {"1mo", "3mo", "6mo", "1y", "2y"}
    if period not in allowed:
        err = SP_6003()
        err.log()
        return JSONResponse(status_code=400, content=err.to_dict())

    prices = await yfinance_client.get_price_history(ticker, period)
    if not prices:
        err = SP_2005(ticker)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    return {"ticker": ticker, "period": period, "data": prices}


def _determine_signal(buy: int, neutral: int, sell: int) -> str:
    if buy > sell * 1.5:
        return "Strong Buy"
    if buy > sell:
        return "Buy"
    if sell > buy * 1.5:
        return "Strong Sell"
    if sell > buy:
        return "Sell"
    return "Neutral"


@router.get("/stock/{ticker}/technical-summary")
async def get_technical_summary(ticker: str):
    ticker = _resolve_kr_ticker(ticker)
    cache_key = f"tech_summary:{ticker}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        import pandas as pd
        from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
        from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator, CCIIndicator
        from ta.volatility import BollingerBands

        prices = await yfinance_client.get_price_history(ticker, "6mo")
        if not prices:
            err = SP_2005(ticker)
            err.log()
            return JSONResponse(status_code=404, content=err.to_dict())

        df = pd.DataFrame(prices)
        close = df["close"]
        high = df["high"]
        low = df["low"]
        current_price = close.iloc[-1]

        ma_results = []
        for period in [5, 10, 20, 50, 100, 200]:
            if len(close) < period:
                continue
            sma_val = SMAIndicator(close, window=period).sma_indicator().iloc[-1]
            ema_val = EMAIndicator(close, window=period).ema_indicator().iloc[-1]

            sma_signal = "Buy" if current_price > sma_val else ("Sell" if current_price < sma_val else "Neutral")
            ema_signal = "Buy" if current_price > ema_val else ("Sell" if current_price < ema_val else "Neutral")

            ma_results.append({"name": f"SMA ({period})", "value": round(sma_val, 2), "signal": sma_signal})
            ma_results.append({"name": f"EMA ({period})", "value": round(ema_val, 2), "signal": ema_signal})

        oscillator_results = []

        rsi_val = RSIIndicator(close, window=14).rsi().iloc[-1]
        rsi_signal = "Buy" if rsi_val < 30 else ("Sell" if rsi_val > 70 else "Neutral")
        oscillator_results.append({"name": "RSI (14)", "value": round(rsi_val, 2), "signal": rsi_signal})

        macd_ind = MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_val = macd_ind.macd().iloc[-1]
        macd_signal_val = macd_ind.macd_signal().iloc[-1]
        macd_signal = "Buy" if macd_val > macd_signal_val else "Sell"
        oscillator_results.append({"name": "MACD (12,26,9)", "value": round(macd_val, 2), "signal": macd_signal})

        stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = stoch.stoch().iloc[-1]
        stoch_d = stoch.stoch_signal().iloc[-1]
        stoch_signal = "Buy" if stoch_k < 20 else ("Sell" if stoch_k > 80 else "Neutral")
        oscillator_results.append({"name": "Stochastic %K (14,3)", "value": round(stoch_k, 2), "signal": stoch_signal})
        oscillator_results.append({"name": "Stochastic %D", "value": round(stoch_d, 2), "signal": stoch_signal})

        cci_val = CCIIndicator(high, low, close, window=20).cci().iloc[-1]
        cci_signal = "Buy" if cci_val < -100 else ("Sell" if cci_val > 100 else "Neutral")
        oscillator_results.append({"name": "CCI (20)", "value": round(cci_val, 2), "signal": cci_signal})

        adx_ind = ADXIndicator(high, low, close, window=14)
        adx_val = adx_ind.adx().iloc[-1]
        price_rising = close.iloc[-1] > close.iloc[-5] if len(close) >= 5 else True
        if adx_val > 25:
            adx_signal = "Buy" if price_rising else "Sell"
        else:
            adx_signal = "Neutral"
        oscillator_results.append({"name": "ADX (14)", "value": round(adx_val, 2), "signal": adx_signal})

        wr_val = WilliamsRIndicator(high, low, close, lbp=14).williams_r().iloc[-1]
        wr_signal = "Buy" if wr_val < -80 else ("Sell" if wr_val > -20 else "Neutral")
        oscillator_results.append({"name": "Williams %R (14)", "value": round(wr_val, 2), "signal": wr_signal})

        bb = BollingerBands(close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_middle = bb.bollinger_mavg().iloc[-1]
        bb_signal = "Buy" if current_price < bb_lower else ("Sell" if current_price > bb_upper else "Neutral")
        oscillator_results.append({"name": "Bollinger Bands (20,2)", "value": round(bb_middle, 2), "signal": bb_signal})

        ma_buy = sum(1 for m in ma_results if m["signal"] == "Buy")
        ma_neutral = sum(1 for m in ma_results if m["signal"] == "Neutral")
        ma_sell = sum(1 for m in ma_results if m["signal"] == "Sell")

        osc_buy = sum(1 for o in oscillator_results if o["signal"] == "Buy")
        osc_neutral = sum(1 for o in oscillator_results if o["signal"] == "Neutral")
        osc_sell = sum(1 for o in oscillator_results if o["signal"] == "Sell")

        total_buy = ma_buy + osc_buy
        total_neutral = ma_neutral + osc_neutral
        total_sell = ma_sell + osc_sell

        result = {
            "ticker": ticker.upper(),
            "summary": {
                "overall": {
                    "buy": total_buy, "neutral": total_neutral, "sell": total_sell,
                    "signal": _determine_signal(total_buy, total_neutral, total_sell),
                },
                "moving_averages": {
                    "buy": ma_buy, "neutral": ma_neutral, "sell": ma_sell,
                    "signal": _determine_signal(ma_buy, ma_neutral, ma_sell),
                },
                "oscillators": {
                    "buy": osc_buy, "neutral": osc_neutral, "sell": osc_sell,
                    "signal": _determine_signal(osc_buy, osc_neutral, osc_sell),
                },
            },
            "moving_averages": ma_results,
            "oscillators": oscillator_results,
        }

        await cache.set(cache_key, result, ttl=900)
        return result

    except Exception as e:
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/stock/{ticker}/pivot-points")
async def get_pivot_points(ticker: str):
    ticker = _resolve_kr_ticker(ticker)
    cache_key = f"pivot_points:{ticker}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        prices = await yfinance_client.get_price_history(ticker, "5d")
        if not prices or len(prices) < 2:
            err = SP_2005(ticker)
            err.log()
            return JSONResponse(status_code=404, content=err.to_dict())

        last_day = prices[-2]
        h = last_day["high"]
        l = last_day["low"]
        c = last_day["close"]

        p = (h + l + c) / 3
        hl = h - l

        classic = {
            "pivot": round(p, 2),
            "r1": round(2 * p - l, 2),
            "r2": round(p + hl, 2),
            "r3": round(h + 2 * (p - l), 2),
            "s1": round(2 * p - h, 2),
            "s2": round(p - hl, 2),
            "s3": round(l - 2 * (h - p), 2),
        }

        fibonacci = {
            "pivot": round(p, 2),
            "r1": round(p + 0.382 * hl, 2),
            "r2": round(p + 0.618 * hl, 2),
            "r3": round(p + hl, 2),
            "s1": round(p - 0.382 * hl, 2),
            "s2": round(p - 0.618 * hl, 2),
            "s3": round(p - hl, 2),
        }

        result = {
            "ticker": ticker.upper(),
            "classic": classic,
            "fibonacci": fibonacci,
        }

        await cache.set(cache_key, result, ttl=3600)
        return result

    except Exception as e:
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    results = await ticker_resolver_service.search_candidates(q, country_code="KR", limit=15)
    for item in results[:10]:
        try:
            info = await yfinance_client.get_stock_info(item["ticker"])
            item["name"] = info.get("name", item["ticker"])
        except Exception:
            item["name"] = item["ticker"]

    return results[:15]


@router.get("/ticker/resolve")
async def resolve_ticker(query: str = Query(..., min_length=1), country_code: str = "KR"):
    try:
        resolution = ticker_resolver_service.resolve_ticker(query, country_code)
        if resolution.get("ticker"):
            try:
                info = await yfinance_client.get_stock_info(resolution["ticker"])
                resolution["name"] = info.get("name", resolution["ticker"])
            except Exception:
                resolution["name"] = resolution["ticker"]
        return resolution
    except Exception as exc:
        err = SP_5010(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/stock/{ticker}/forecast-delta")
async def get_stock_forecast_delta(ticker: str, limit: int = 8):
    try:
        resolution = ticker_resolver_service.resolve_ticker(ticker, "KR")
        return await forecast_monitor_service.get_stock_forecast_delta(resolution["ticker"], limit=limit)
    except Exception as exc:
        err = SP_5014(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
