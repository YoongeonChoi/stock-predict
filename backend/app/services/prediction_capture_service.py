"""Centralized prediction capture helpers for research lab accumulation."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.analysis.stock_analyzer import analyze_stock
from app.database import db
from app.runtime import get_or_create_background_job

log = logging.getLogger(__name__)

MULTI_HORIZON_PREDICTION_TYPES = {
    5: "distributional_5d",
    20: "distributional_20d",
}
OPPORTUNITY_CAPTURE_LIMIT = 6
ARCHIVE_BACKFILL_LIMIT = 25
_stock_capture_semaphore: asyncio.Semaphore | None = None


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _prediction_symbol(report_type: str, report: dict, ticker: str | None) -> str | None:
    if ticker:
        return ticker
    if report_type == "country":
        country = report.get("country", {})
        indices = country.get("indices", [])
        if indices:
            return indices[0].get("ticker")
    return None


def _resolve_country_code(report: dict, country_code: str | None) -> str | None:
    return country_code or report.get("country_code") or report.get("country", {}).get("code")


def _driver_rows_from_texts(items: list[str] | None) -> list[dict] | None:
    cleaned = [str(item).strip() for item in (items or []) if str(item).strip()]
    if not cleaned:
        return None
    return [{"signal": "context", "detail": item} for item in cleaned[:3]]


async def _upsert_prediction_rows(rows: list[dict]) -> int:
    captured = 0
    for row in rows:
        target_date = str(row.get("target_date") or "").strip()
        symbol = str(row.get("symbol") or "").strip().upper()
        reference_price = float(row.get("reference_price") or 0.0)
        predicted_close = float(row.get("predicted_close") or 0.0)
        if not target_date or not symbol or reference_price <= 0 or predicted_close <= 0:
            continue
        await db.prediction_upsert(
            scope=str(row["scope"]),
            symbol=symbol,
            country_code=row.get("country_code"),
            prediction_type=str(row["prediction_type"]),
            target_date=target_date,
            reference_date=row.get("reference_date"),
            reference_price=reference_price,
            predicted_close=predicted_close,
            predicted_low=row.get("predicted_low"),
            predicted_high=row.get("predicted_high"),
            up_probability=row.get("up_probability"),
            confidence=row.get("confidence"),
            direction=row.get("direction"),
            drivers_json=row.get("drivers_json"),
            calibration_json=row.get("calibration_json"),
            model_version=row.get("model_version"),
        )
        captured += 1
    return captured


def _build_report_prediction_rows(
    *,
    report_type: str,
    report: dict,
    country_code: str | None,
    ticker: str | None,
) -> list[dict]:
    rows: list[dict] = []
    symbol = _prediction_symbol(report_type, report, ticker)
    resolved_country_code = _resolve_country_code(report, country_code)
    next_day = report.get("next_day_forecast")
    if isinstance(next_day, dict) and symbol and next_day.get("reference_price") is not None:
        rows.append(
            {
                "scope": report_type,
                "symbol": symbol,
                "country_code": resolved_country_code,
                "prediction_type": "next_day",
                "target_date": next_day.get("target_date", ""),
                "reference_date": next_day.get("reference_date"),
                "reference_price": float(next_day.get("reference_price", 0) or 0),
                "predicted_close": float(next_day.get("predicted_close", 0) or 0),
                "predicted_low": next_day.get("predicted_low"),
                "predicted_high": next_day.get("predicted_high"),
                "up_probability": next_day.get("up_probability"),
                "confidence": next_day.get("confidence"),
                "direction": next_day.get("direction"),
                "drivers_json": next_day.get("drivers"),
                "calibration_json": next_day.get("calibration_snapshot"),
                "model_version": next_day.get("model_version"),
            }
        )

    free_kr = report.get("free_kr_forecast")
    if isinstance(free_kr, dict) and symbol and free_kr.get("reference_price") is not None:
        evidence = free_kr.get("evidence")
        model_version = free_kr.get("model_version")
        horizons = free_kr.get("horizons") or []
        for horizon in horizons:
            if not isinstance(horizon, dict):
                continue
            horizon_days = int(horizon.get("horizon_days") or 0)
            prediction_type = MULTI_HORIZON_PREDICTION_TYPES.get(horizon_days)
            if not prediction_type:
                continue
            p_up = float(horizon.get("p_up") or 0.0)
            p_down = float(horizon.get("p_down") or 0.0)
            p_flat = float(horizon.get("p_flat") or 0.0)
            if p_up >= max(p_down, p_flat):
                direction = "up"
            elif p_down >= max(p_up, p_flat):
                direction = "down"
            else:
                direction = "flat"
            rows.append(
                {
                    "scope": report_type,
                    "symbol": symbol,
                    "country_code": resolved_country_code,
                    "prediction_type": prediction_type,
                    "target_date": horizon.get("target_date", ""),
                    "reference_date": free_kr.get("reference_date"),
                    "reference_price": float(free_kr.get("reference_price", 0) or 0),
                    "predicted_close": float(horizon.get("price_q50") or 0),
                    "predicted_low": horizon.get("price_q10"),
                    "predicted_high": horizon.get("price_q90"),
                    "up_probability": horizon.get("p_up"),
                    "confidence": horizon.get("confidence"),
                    "direction": direction,
                    "drivers_json": evidence,
                    "calibration_json": horizon.get("calibration_snapshot"),
                    "model_version": model_version,
                }
            )
    return rows


async def capture_report_predictions(
    report_type: str,
    report: dict,
    *,
    country_code: str | None = None,
    ticker: str | None = None,
) -> dict:
    if not isinstance(report, dict):
        return {"captured_predictions": 0, "prediction_types": []}
    rows = _build_report_prediction_rows(
        report_type=report_type,
        report=report,
        country_code=country_code,
        ticker=ticker,
    )
    captured = await _upsert_prediction_rows(rows)
    return {
        "captured_predictions": captured,
        "prediction_types": [row["prediction_type"] for row in rows],
    }


async def _capture_opportunity_focus(country_code: str, focus: dict) -> int:
    ticker = str(focus.get("ticker") or "").upper()
    next_day = focus.get("next_day_forecast")
    if not ticker or not isinstance(next_day, dict):
        return 0
    rows = _build_report_prediction_rows(
        report_type="stock",
        report={"next_day_forecast": next_day},
        country_code=country_code,
        ticker=ticker,
    )
    return await _upsert_prediction_rows(rows)


def _build_opportunity_prediction_rows(country_code: str, payload: dict, limit: int) -> list[dict]:
    rows: list[dict] = []
    for item in list(payload.get("opportunities") or [])[: max(limit, 0)]:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        target_date = str(item.get("target_date_20d") or item.get("forecast_date") or "").strip()
        reference_price = float(item.get("current_price") or 0.0)
        if not ticker or not target_date or reference_price <= 0:
            continue
        predicted_close = float(
            item.get("price_q50_20d")
            or item.get("base_case_price")
            or reference_price * (1.0 + float(item.get("expected_return_pct_20d") or item.get("predicted_return_pct") or 0.0) / 100.0)
        )
        predicted_low = item.get("price_q25_20d") or item.get("bear_case_price")
        predicted_high = item.get("price_q75_20d") or item.get("bull_case_price")
        p_up = float(item.get("up_probability_20d") or item.get("up_probability") or 0.0)
        p_down = float(item.get("down_probability_20d") or item.get("bear_probability") or 0.0)
        p_flat = float(item.get("flat_probability_20d") or item.get("base_probability") or 0.0)
        if p_up >= max(p_down, p_flat):
            direction = "up"
        elif p_down >= max(p_up, p_flat):
            direction = "down"
        else:
            direction = "flat"
        rows.append(
            {
                "scope": "stock",
                "symbol": ticker,
                "country_code": country_code,
                "prediction_type": "distributional_20d",
                "target_date": target_date,
                "reference_date": _utc_today(),
                "reference_price": reference_price,
                "predicted_close": predicted_close,
                "predicted_low": predicted_low,
                "predicted_high": predicted_high,
                "up_probability": item.get("up_probability_20d") or item.get("up_probability"),
                "confidence": item.get("distribution_confidence_20d") or item.get("confidence"),
                "direction": direction,
                "drivers_json": _driver_rows_from_texts(item.get("thesis")),
                "calibration_json": {
                    "prediction_type": "distributional_20d",
                    "raw_confidence": item.get("raw_confidence_20d"),
                    "calibrated_probability": item.get("calibrated_probability_20d"),
                    "probability_edge": item.get("probability_edge_20d"),
                    "analog_support": item.get("analog_support_20d"),
                    "regime_support": item.get("regime_support_20d"),
                    "agreement_support": item.get("agreement_support_20d"),
                    "data_quality_support": item.get("data_quality_support_20d"),
                    "confidence_calibrator": item.get("confidence_calibrator_20d"),
                },
                "model_version": "opportunity_radar_20d",
            }
        )
    return rows


async def capture_market_opportunity_predictions(
    country_code: str,
    payload: dict,
    *,
    limit: int = OPPORTUNITY_CAPTURE_LIMIT,
) -> dict:
    if not isinstance(payload, dict):
        return {"captured_predictions": 0, "captured_focus": 0, "captured_opportunities": 0}

    captured_focus = 0
    if isinstance(payload.get("next_day_focus"), dict):
        captured_focus = await _capture_opportunity_focus(country_code, payload["next_day_focus"])

    rows = _build_opportunity_prediction_rows(country_code, payload, limit)
    captured_opportunities = await _upsert_prediction_rows(rows)
    return {
        "captured_predictions": captured_focus + captured_opportunities,
        "captured_focus": captured_focus,
        "captured_opportunities": captured_opportunities,
    }


async def _report_prediction_rows_missing(rows: list[dict]) -> bool:
    for row in rows:
        exists = await db.prediction_record_exists(
            scope=str(row["scope"]),
            symbol=str(row["symbol"]),
            prediction_type=str(row["prediction_type"]),
            target_date=str(row["target_date"]),
        )
        if not exists:
            return True
    return False


async def backfill_recent_archive_predictions(limit: int = ARCHIVE_BACKFILL_LIMIT) -> dict:
    rows = await db.archive_list(limit=max(int(limit), 1))
    checked_reports = 0
    updated_reports = 0
    captured_predictions = 0
    for row in rows:
        report_json = row.get("report_json")
        if not isinstance(report_json, dict):
            try:
                report_json = json.loads(report_json or "{}")
            except (TypeError, json.JSONDecodeError):
                report_json = {}
        if not isinstance(report_json, dict):
            continue
        report_type = str(row.get("report_type") or "").strip()
        checked_reports += 1
        prediction_rows = _build_report_prediction_rows(
            report_type=report_type,
            report=report_json,
            country_code=row.get("country_code"),
            ticker=row.get("ticker"),
        )
        if not prediction_rows:
            continue
        if not await _report_prediction_rows_missing(prediction_rows):
            continue
        captured = await _upsert_prediction_rows(prediction_rows)
        if captured > 0:
            updated_reports += 1
            captured_predictions += captured
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checked_reports": checked_reports,
        "updated_reports": updated_reports,
        "captured_predictions": captured_predictions,
    }


def _stock_capture_semaphore_limit() -> int:
    try:
        from app.config import get_settings

        settings = get_settings()
        return 1 if settings.startup_memory_safe_mode else 2
    except Exception:
        return 1


def _get_stock_capture_semaphore() -> asyncio.Semaphore:
    global _stock_capture_semaphore
    if _stock_capture_semaphore is None:
        _stock_capture_semaphore = asyncio.Semaphore(_stock_capture_semaphore_limit())
    return _stock_capture_semaphore


async def _stock_distributional_capture_needed(ticker: str) -> bool:
    today = _utc_today()
    for prediction_type in ("distributional_5d", "distributional_20d"):
        rows = await db.prediction_symbol_history(
            symbol=ticker,
            scope="stock",
            prediction_type=prediction_type,
            limit=1,
        )
        latest = rows[0] if rows else None
        if not latest:
            return True
        if str(latest.get("target_date") or "") < today:
            return True
    return False


async def schedule_stock_distributional_capture(ticker: str) -> bool:
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return False
    if not await _stock_distributional_capture_needed(ticker):
        return False

    async def _run_capture() -> None:
        semaphore = _get_stock_capture_semaphore()
        async with semaphore:
            detail = await analyze_stock(ticker)
            await capture_report_predictions("stock", detail, ticker=ticker)

    _, created = get_or_create_background_job(f"stock_prediction_capture:{ticker}", _run_capture)
    return created
