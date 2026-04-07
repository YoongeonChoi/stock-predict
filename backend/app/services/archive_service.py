"""Report archiving and prediction accuracy tracking."""

import asyncio
import json
from datetime import datetime

from app.data import cache
from app.data import yfinance_client
from app.database import db
from app.services import prediction_capture_service
PREDICTION_ACCURACY_CACHE_TTL_SECONDS = 300
PREDICTION_ACCURACY_WAIT_TIMEOUT_SECONDS = 2.0
PREDICTION_ACCURACY_REFRESH_TIMEOUT_SECONDS = 8.0


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
    await prediction_capture_service.capture_report_predictions(
        report_type,
        report,
        country_code=country_code,
        ticker=ticker,
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
