"""Report archiving and prediction accuracy tracking."""

import asyncio
import json
from datetime import datetime

from app.data import cache
from app.data import yfinance_client
from app.database import db

MULTI_HORIZON_PREDICTION_TYPES = {
    5: "distributional_5d",
    20: "distributional_20d",
}
PREDICTION_ACCURACY_CACHE_TTL_SECONDS = 300
PREDICTION_ACCURACY_WAIT_TIMEOUT_SECONDS = 2.0
PREDICTION_ACCURACY_REFRESH_TIMEOUT_SECONDS = 8.0


def _prediction_symbol(report_type: str, report: dict, ticker: str | None) -> str | None:
    if ticker:
        return ticker
    if report_type == "country":
        country = report.get("country", {})
        indices = country.get("indices", [])
        if indices:
            return indices[0].get("ticker")
    return None


async def save_report(
    report_type: str,
    report: dict,
    country_code: str | None = None,
    sector_id: str | None = None,
    ticker: str | None = None,
) -> int:
    scores = report.get("score")
    predictions = None
    if "next_day_forecast" in report:
        predictions = report["next_day_forecast"]
    elif "forecast" in report:
        predictions = report["forecast"]
    elif "buy_sell_guide" in report:
        predictions = report["buy_sell_guide"]

    report_id = await db.archive_save(
        report_type=report_type,
        report_json=report,
        country_code=country_code,
        sector_id=sector_id,
        ticker=ticker,
        scores_json=scores,
        predictions_json=predictions,
    )

    next_day = report.get("next_day_forecast")
    symbol = _prediction_symbol(report_type, report, ticker)
    if isinstance(next_day, dict) and symbol and next_day.get("reference_price") is not None:
        await db.prediction_upsert(
            scope=report_type,
            symbol=symbol,
            country_code=country_code or report.get("country_code") or report.get("country", {}).get("code"),
            prediction_type="next_day",
            target_date=next_day.get("target_date", ""),
            reference_date=next_day.get("reference_date"),
            reference_price=float(next_day.get("reference_price", 0)),
            predicted_close=float(next_day.get("predicted_close", 0)),
            predicted_low=next_day.get("predicted_low"),
            predicted_high=next_day.get("predicted_high"),
            up_probability=next_day.get("up_probability"),
            confidence=next_day.get("confidence"),
            direction=next_day.get("direction"),
            drivers_json=next_day.get("drivers"),
            calibration_json=next_day.get("calibration_snapshot"),
            model_version=next_day.get("model_version"),
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
            await db.prediction_upsert(
                scope=report_type,
                symbol=symbol,
                country_code=country_code or report.get("country_code") or report.get("country", {}).get("code"),
                prediction_type=prediction_type,
                target_date=horizon.get("target_date", ""),
                reference_date=free_kr.get("reference_date"),
                reference_price=float(free_kr.get("reference_price", 0)),
                predicted_close=float(horizon.get("price_q50") or 0),
                predicted_low=horizon.get("price_q10"),
                predicted_high=horizon.get("price_q90"),
                up_probability=horizon.get("p_up"),
                confidence=horizon.get("confidence"),
                direction=direction,
                drivers_json=evidence,
                calibration_json=horizon.get("calibration_snapshot"),
                model_version=model_version,
            )

    return report_id


async def list_reports(
    report_type: str | None = None,
    country_code: str | None = None,
    limit: int = 50,
) -> list[dict]:
    rows = await db.archive_list(report_type, country_code, limit)
    results = []
    for row in rows:
        preview = ""
        try:
            report_json = json.loads(row.get("report_json", "{}"))
            preview = report_json.get("market_summary", report_json.get("summary", ""))[:200]
        except (json.JSONDecodeError, AttributeError):
            pass
        results.append({
            "id": row["id"],
            "report_type": row["report_type"],
            "country_code": row.get("country_code"),
            "sector_id": row.get("sector_id"),
            "ticker": row.get("ticker"),
            "created_at": row["created_at"],
            "preview": preview,
        })
    return results


async def get_report(report_id: int) -> dict | None:
    row = await db.archive_get(report_id)
    if not row:
        return None
    try:
        row["report_json"] = json.loads(row["report_json"])
        if row.get("scores_json"):
            row["scores_json"] = json.loads(row["scores_json"])
        if row.get("predictions_json"):
            row["predictions_json"] = json.loads(row["predictions_json"])
    except (json.JSONDecodeError, TypeError):
        pass
    return row


async def refresh_prediction_accuracy(limit: int = 200) -> dict:
    pending = await db.prediction_pending(datetime.now().date().isoformat(), limit=limit)
    evaluated_count = 0
    unmatched_count = 0
    error_count = 0
    for record in pending:
        try:
            prices = await yfinance_client.get_price_history(record["symbol"], period="1y")
        except Exception:
            error_count += 1
            continue

        matched = next((row for row in prices if row.get("date") == record["target_date"]), None)
        if not matched:
            unmatched_count += 1
            continue

        await db.prediction_update_actual(
            record_id=record["id"],
            actual_close=float(matched.get("close", 0)),
            actual_low=matched.get("low"),
            actual_high=matched.get("high"),
        )
        evaluated_count += 1

    calibration_refreshed = False
    if evaluated_count > 0:
        from app.services import confidence_calibration_service

        await confidence_calibration_service.refresh_empirical_profiles()
        calibration_refreshed = True

    return {
        "checked_at": datetime.now().isoformat(),
        "due_pending_count": len(pending),
        "evaluated_count": evaluated_count,
        "unmatched_count": unmatched_count,
        "error_count": error_count,
        "calibration_refreshed": calibration_refreshed,
    }


def _build_accuracy_payload(
    stats: dict | None = None,
    *,
    partial: bool = False,
    fallback_reason: str | None = None,
) -> dict:
    payload = {
        "stored_predictions": 0,
        "pending_predictions": 0,
        "total_predictions": 0,
        "within_range": 0,
        "within_range_rate": 0.0,
        "direction_hits": 0,
        "direction_accuracy": 0.0,
        "avg_error_pct": 0.0,
        "avg_confidence": 0.0,
    }
    if isinstance(stats, dict):
        payload.update(stats)
    payload["generated_at"] = datetime.now().isoformat()
    if partial:
        payload["partial"] = True
        payload["fallback_reason"] = fallback_reason
    return payload


async def get_accuracy(refresh: bool = False) -> dict:
    cache_key = f"prediction_accuracy:v2:{int(refresh)}"

    async def _fetch_accuracy():
        partial_reason: str | None = None
        if refresh:
            try:
                await asyncio.wait_for(
                    refresh_prediction_accuracy(),
                    timeout=PREDICTION_ACCURACY_REFRESH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                partial_reason = "prediction_accuracy_refresh_timeout"
            except Exception:
                partial_reason = "prediction_accuracy_refresh_error"
        try:
            stats = await db.prediction_stats("next_day")
            return _build_accuracy_payload(
                stats,
                partial=partial_reason is not None,
                fallback_reason=partial_reason,
            )
        except Exception:
            reason = partial_reason or "prediction_accuracy_stats_error"
            return _build_accuracy_payload(partial=True, fallback_reason=reason)

    return await cache.get_or_fetch(
        cache_key,
        _fetch_accuracy,
        ttl=PREDICTION_ACCURACY_CACHE_TTL_SECONDS,
        wait_timeout=PREDICTION_ACCURACY_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: _build_accuracy_payload(
            partial=True,
            fallback_reason="prediction_accuracy_cache_wait_timeout",
        ),
    )
