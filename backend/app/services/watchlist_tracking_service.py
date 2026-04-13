from __future__ import annotations

import asyncio
from typing import Any

from app.analysis.stock_analyzer import (
    analyze_stock,
    build_quick_stock_detail,
    get_cached_quick_stock_detail,
    get_cached_stock_detail,
)
from app.data.supabase_client import supabase_client
from app.services import forecast_monitor_service, ticker_resolver_service

TRACKING_DETAIL_HISTORY_LIMIT = 8
TRACKING_DETAIL_ANALYZE_TIMEOUT_SECONDS = 12.0


def _direction_label(direction: str | None) -> str:
    return {"up": "상승", "down": "하락", "flat": "보합"}.get(str(direction or ""), "없음")


def _coerce_history_payload(history_payload: Any) -> dict[str, Any]:
    if isinstance(history_payload, dict):
        history = history_payload.get("history")
        summary = history_payload.get("summary") if isinstance(history_payload.get("summary"), dict) else {}
        return {
            "generated_at": history_payload.get("generated_at"),
            "ticker": history_payload.get("ticker"),
            "summary": summary,
            "history": history if isinstance(history, list) else [],
        }
    if isinstance(history_payload, list):
        return {
            "generated_at": None,
            "ticker": None,
            "summary": {},
            "history": [item for item in history_payload if isinstance(item, dict)],
        }
    return {
        "generated_at": None,
        "ticker": None,
        "summary": {},
        "history": [],
    }


def _panel_state(available: bool, *, inactive: bool = False) -> str:
    if inactive:
        return "inactive"
    return "ready" if available else "degraded"


def _history_preview(history_payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = _coerce_history_payload(history_payload)
    history = normalized_payload.get("history") or []
    latest = history[0] if history else None
    summary = normalized_payload.get("summary") or {}
    return {
        "last_prediction_at": latest.get("created_at") if latest else None,
        "last_outlook_label": summary.get("current_direction_label") or (latest.get("direction_label") if latest else None),
        "last_confidence": latest.get("confidence") if latest else None,
    }


def _build_realized_accuracy_summary(history_payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = _coerce_history_payload(history_payload)
    history = normalized_payload.get("history") or []
    evaluated = [item for item in history if item.get("direction_hit") is not None]
    if not history:
        return {
            "available": False,
            "sample_count": 0,
            "evaluated_count": 0,
            "direction_hit_rate": None,
            "average_absolute_error_pct": None,
            "message": "이 종목의 저장된 예측 이력이 아직 부족합니다.",
        }
    if not evaluated:
        return {
            "available": False,
            "sample_count": len(history),
            "evaluated_count": 0,
            "direction_hit_rate": None,
            "average_absolute_error_pct": None,
            "message": "실제 종가가 확정된 기록이 부족해 적중률은 아직 집계 중입니다.",
        }

    abs_errors: list[float] = []
    for item in evaluated:
        actual_close = item.get("actual_close")
        predicted_close = item.get("predicted_close")
        if actual_close in (None, 0) or predicted_close in (None, 0):
            continue
        abs_errors.append(abs(float(predicted_close) - float(actual_close)) / float(actual_close) * 100.0)

    hit_rate = round(sum(1 for item in evaluated if item.get("direction_hit")) / len(evaluated) * 100.0, 1)
    average_absolute_error_pct = round(sum(abs_errors) / len(abs_errors), 2) if abs_errors else None
    if average_absolute_error_pct is None:
        message = f"최근 평가 가능한 {len(evaluated)}건 기준 방향 적중률은 {hit_rate:.1f}%입니다."
    else:
        message = (
            f"최근 평가 가능한 {len(evaluated)}건 기준 방향 적중률은 {hit_rate:.1f}%이고 "
            f"평균 오차는 {average_absolute_error_pct:.2f}%입니다."
        )
    return {
        "available": True,
        "sample_count": len(history),
        "evaluated_count": len(evaluated),
        "direction_hit_rate": hit_rate,
        "average_absolute_error_pct": average_absolute_error_pct,
        "message": message,
    }


def _build_current_context_summary(ticker: str, stock_detail: dict[str, Any] | None) -> dict[str, Any]:
    if not stock_detail:
        return {
            "available": False,
            "summary": "현재 판단 근거를 아직 준비하지 못했습니다.",
            "setup_label": None,
            "action": None,
            "market_regime_label": None,
            "confidence_note": None,
            "key_risks": [],
            "key_catalysts": [],
        }

    public_summary = stock_detail.get("public_summary") or {}
    trade_plan = stock_detail.get("trade_plan") or {}
    market_regime = stock_detail.get("market_regime") or {}
    key_risks = public_summary.get("thesis_breakers") or stock_detail.get("key_risks") or []
    key_catalysts = public_summary.get("evidence_for") or stock_detail.get("key_catalysts") or []

    return {
        "available": True,
        "summary": public_summary.get("summary") or stock_detail.get("analysis_summary") or f"{ticker} 현재 판단 근거를 정리하는 중입니다.",
        "setup_label": trade_plan.get("setup_label"),
        "action": trade_plan.get("action"),
        "market_regime_label": market_regime.get("label"),
        "confidence_note": public_summary.get("confidence_note") or stock_detail.get("next_day_forecast", {}).get("confidence_note"),
        "key_risks": key_risks[:4],
        "key_catalysts": key_catalysts[:4],
    }


def _build_latest_snapshot(
    ticker: str,
    watchlist_row: dict[str, Any],
    stock_detail: dict[str, Any] | None,
    history_payload: dict[str, Any],
) -> dict[str, Any]:
    normalized_payload = _coerce_history_payload(history_payload)
    history = normalized_payload.get("history") or []
    history_summary = normalized_payload.get("summary") or {}
    latest_history = history[0] if history else {}
    forecast = (stock_detail or {}).get("next_day_forecast") or {}
    free_kr = (stock_detail or {}).get("free_kr_forecast") or {}
    horizons = free_kr.get("horizons") if isinstance(free_kr, dict) else None
    horizon = horizons[0] if horizons else {}
    context_summary = _build_current_context_summary(ticker, stock_detail)

    direction = forecast.get("direction")
    if not direction and horizon:
        direction = max(
            (("up", horizon.get("p_up") or 0.0), ("flat", horizon.get("p_flat") or 0.0), ("down", horizon.get("p_down") or 0.0)),
            key=lambda item: item[1],
        )[0]
    if not direction:
        direction = history_summary.get("current_direction")

    current_price = (stock_detail or {}).get("current_price")
    if current_price is None:
        current_price = latest_history.get("reference_price")

    return {
        "available": bool(stock_detail or latest_history),
        "ticker": ticker,
        "name": (stock_detail or {}).get("name") or watchlist_row.get("name") or ticker,
        "country_code": watchlist_row.get("country_code") or (stock_detail or {}).get("country_code") or "KR",
        "current_price": current_price,
        "target_date": forecast.get("target_date") or horizon.get("target_date") or latest_history.get("target_date"),
        "predicted_close": forecast.get("predicted_close") or horizon.get("price_q50") or latest_history.get("predicted_close"),
        "predicted_low": forecast.get("predicted_low") or horizon.get("price_q25") or latest_history.get("predicted_low"),
        "predicted_high": forecast.get("predicted_high") or horizon.get("price_q75") or latest_history.get("predicted_high"),
        "direction": direction,
        "direction_label": _direction_label(direction) if direction else history_summary.get("current_direction_label") or "없음",
        "up_probability": forecast.get("up_probability") or horizon.get("p_up") or latest_history.get("up_probability"),
        "confidence": forecast.get("confidence") or horizon.get("confidence") or latest_history.get("confidence"),
        "confidence_note": forecast.get("confidence_note") or context_summary.get("confidence_note"),
        "summary": ((stock_detail or {}).get("public_summary") or {}).get("summary"),
        "generated_at": (stock_detail or {}).get("generated_at") or normalized_payload.get("generated_at"),
        "last_prediction_at": latest_history.get("created_at"),
    }


async def _load_stock_snapshot(ticker: str) -> tuple[dict[str, Any] | None, str | None]:
    cached_full = await get_cached_stock_detail(ticker, refresh_quote=True)
    if cached_full:
        return cached_full, cached_full.get("fallback_reason")

    cached_quick = await get_cached_quick_stock_detail(ticker)
    if cached_quick:
        return cached_quick, cached_quick.get("fallback_reason") or "stock_quick_detail"

    quick_detail = await build_quick_stock_detail(ticker)
    if quick_detail:
        return quick_detail, quick_detail.get("fallback_reason") or "stock_quick_detail"

    try:
        full_detail = await asyncio.wait_for(analyze_stock(ticker), timeout=TRACKING_DETAIL_ANALYZE_TIMEOUT_SECONDS)
        return full_detail, full_detail.get("fallback_reason")
    except Exception:
        return None, "tracking_snapshot_unavailable"


async def get_tracking_preview(ticker: str) -> dict[str, Any]:
    try:
        history_payload = await forecast_monitor_service.get_stock_forecast_delta(ticker, limit=4)
        return _history_preview(history_payload)
    except Exception:
        return {
            "last_prediction_at": None,
            "last_outlook_label": None,
            "last_confidence": None,
        }


async def set_tracking_enabled(user_id: str, ticker: str, country_code: str, enabled: bool) -> dict[str, Any] | None:
    resolution = ticker_resolver_service.resolve_ticker(ticker, country_code)
    normalized_ticker = resolution["ticker"] or ticker.upper()
    row = await supabase_client.watchlist_set_tracking(user_id, normalized_ticker, enabled=enabled)
    if not row:
        return None
    preview = await get_tracking_preview(normalized_ticker)
    return {
        **row,
        "ticker": normalized_ticker,
        "country_code": resolution["country_code"],
        **preview,
    }


async def get_tracking_detail(user_id: str, ticker: str, country_code: str = "KR") -> dict[str, Any] | None:
    resolution = ticker_resolver_service.resolve_ticker(ticker, country_code)
    normalized_ticker = resolution["ticker"] or ticker.upper()
    watchlist_row = await supabase_client.watchlist_get(user_id, normalized_ticker)
    if not watchlist_row:
        return None

    history_payload, stock_snapshot_result = await asyncio.gather(
        forecast_monitor_service.get_stock_forecast_delta(normalized_ticker, limit=TRACKING_DETAIL_HISTORY_LIMIT),
        _load_stock_snapshot(normalized_ticker),
    )
    stock_detail, snapshot_fallback_reason = stock_snapshot_result
    preview = _history_preview(history_payload)
    realized_accuracy_summary = _build_realized_accuracy_summary(history_payload)
    current_context_summary = _build_current_context_summary(normalized_ticker, stock_detail)
    latest_snapshot = _build_latest_snapshot(normalized_ticker, watchlist_row, stock_detail, history_payload)

    tracking_enabled = bool(watchlist_row.get("tracking_enabled"))
    prediction_history_available = bool(history_payload.get("history"))
    snapshot_available = bool(latest_snapshot.get("available"))
    accuracy_available = bool(realized_accuracy_summary.get("available"))
    context_available = bool(current_context_summary.get("available"))

    panel_states = {
        "latest_snapshot": _panel_state(snapshot_available),
        "prediction_history": _panel_state(prediction_history_available, inactive=not tracking_enabled),
        "realized_accuracy": _panel_state(accuracy_available, inactive=not tracking_enabled),
        "current_context": _panel_state(context_available),
    }

    partial = (not snapshot_available) or (tracking_enabled and (not prediction_history_available or not context_available))
    fallback_reason = None
    if not snapshot_available:
        fallback_reason = snapshot_fallback_reason or "tracking_snapshot_unavailable"
    elif tracking_enabled and not prediction_history_available:
        fallback_reason = "tracking_history_pending"

    return {
        "watchlist_meta": {
            "id": watchlist_row.get("id"),
            "ticker": normalized_ticker,
            "country_code": resolution["country_code"],
            "added_at": watchlist_row.get("added_at"),
            "tracking_enabled": tracking_enabled,
            "tracking_started_at": watchlist_row.get("tracking_started_at"),
            "tracking_updated_at": watchlist_row.get("tracking_updated_at"),
            "name": latest_snapshot.get("name"),
            "current_price": latest_snapshot.get("current_price"),
            **preview,
        },
        "tracking_state": "active" if tracking_enabled else "inactive",
        "latest_snapshot": latest_snapshot,
        "prediction_change_summary": history_payload.get("summary") or {
            "available": False,
            "message": "이 종목의 저장된 예측 이력이 아직 부족합니다.",
        },
        "prediction_history": history_payload.get("history") or [],
        "realized_accuracy_summary": realized_accuracy_summary,
        "current_context_summary": current_context_summary,
        "partial": partial,
        "fallback_reason": fallback_reason,
        "panel_states": panel_states,
    }
