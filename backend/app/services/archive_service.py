"""Report archiving and prediction accuracy tracking."""

import asyncio
import json
from datetime import datetime

from app.data import cache
from app.data import yfinance_client
from app.database import db
from app.services import opportunity_radar_lab_service, prediction_capture_service
PREDICTION_ACCURACY_CACHE_TTL_SECONDS = 300
PREDICTION_ACCURACY_WAIT_TIMEOUT_SECONDS = 2.0
PREDICTION_ACCURACY_REFRESH_TIMEOUT_SECONDS = 8.0


def _parse_json_dict(raw_value) -> dict:
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price_window_rows(prices: list[dict], *, reference_date: str | None, target_date: str) -> list[dict]:
    target = str(target_date or "")[:10]
    reference = str(reference_date or "")[:10]
    if not target:
        return []
    rows = []
    for item in prices:
        current_date = str(item.get("date") or "")[:10]
        if not current_date:
            continue
        if reference and current_date <= reference:
            continue
        if current_date <= target:
            rows.append(item)
    return rows


def _window_extremes(rows: list[dict], fallback_row: dict) -> tuple[float | None, float | None]:
    lows = [_safe_float(item.get("low")) for item in rows]
    highs = [_safe_float(item.get("high")) for item in rows]
    lows = [value for value in lows if value is not None and value > 0]
    highs = [value for value in highs if value is not None and value > 0]
    if not lows:
        low = _safe_float(fallback_row.get("low"))
        lows = [low] if low is not None and low > 0 else []
    if not highs:
        high = _safe_float(fallback_row.get("high"))
        highs = [high] if high is not None and high > 0 else []
    return (min(lows) if lows else None, max(highs) if highs else None)


def _between_window(value: float | None, low: float | None, high: float | None) -> bool | None:
    if value is None or low is None or high is None:
        return None
    return low <= value <= high


def _zone_touched(zone_low: float | None, zone_high: float | None, low: float | None, high: float | None) -> bool | None:
    if zone_low is None or zone_high is None or low is None or high is None:
        return None
    return low <= zone_high and high >= zone_low


def _build_weekly_execution_evaluation(record: dict, *, target_row: dict, window_low: float | None, window_high: float | None) -> dict | None:
    calibration = _parse_json_dict(record.get("calibration_json"))
    plan = calibration.get("weekly_trade_plan")
    if not isinstance(plan, dict):
        return None

    buy_price = _safe_float(plan.get("buy_price"))
    buy_zone_low = _safe_float(plan.get("buy_zone_low"))
    buy_zone_high = _safe_float(plan.get("buy_zone_high"))
    sell_price = _safe_float(plan.get("sell_price"))
    sell_zone_low = _safe_float(plan.get("sell_zone_low"))
    sell_zone_high = _safe_float(plan.get("sell_zone_high"))
    stop_loss = _safe_float(plan.get("stop_loss"))
    reference_price = _safe_float(record.get("reference_price"))
    actual_close = _safe_float(target_row.get("close"))

    buy_price_touched = _between_window(buy_price, window_low, window_high)
    buy_zone_touched = _zone_touched(buy_zone_low, buy_zone_high, window_low, window_high)
    sell_price_touched = _between_window(sell_price, window_low, window_high)
    sell_zone_touched = _zone_touched(sell_zone_low, sell_zone_high, window_low, window_high)
    stop_loss_touched = bool(window_low is not None and stop_loss is not None and window_low <= stop_loss)

    if sell_zone_touched and stop_loss_touched:
        outcome = "target_and_stop_touched_order_unknown"
    elif sell_zone_touched:
        outcome = "target_zone_touched"
    elif stop_loss_touched:
        outcome = "stop_loss_touched"
    elif buy_zone_touched or buy_price_touched:
        outcome = "entry_touched"
    else:
        outcome = "not_triggered"

    return {
        "kind": "weekly_trade_plan",
        "prediction_type": record.get("prediction_type"),
        "target_date": record.get("target_date"),
        "reference_date": record.get("reference_date"),
        "action": plan.get("action"),
        "buy_price": buy_price,
        "buy_zone_low": buy_zone_low,
        "buy_zone_high": buy_zone_high,
        "sell_price": sell_price,
        "sell_zone_low": sell_zone_low,
        "sell_zone_high": sell_zone_high,
        "stop_loss": stop_loss,
        "window_low": window_low,
        "window_high": window_high,
        "actual_close": actual_close,
        "buy_price_touched": buy_price_touched,
        "buy_zone_touched": buy_zone_touched,
        "sell_price_touched": sell_price_touched,
        "sell_zone_touched": sell_zone_touched,
        "stop_loss_touched": stop_loss_touched,
        "actual_return_pct": (
            round((actual_close - reference_price) / reference_price * 100.0, 2)
            if actual_close is not None and reference_price
            else None
        ),
        "outcome": outcome,
        "note": "5거래일 실행안은 target date 종가와 reference 이후 target date까지의 고저 범위로 평가합니다. 일중 선후관계는 확정하지 않습니다.",
    }


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
        window_rows = _price_window_rows(
            prices,
            reference_date=record.get("reference_date"),
            target_date=record["target_date"],
        )
        actual_window_low, actual_window_high = _window_extremes(window_rows, matched)
        execution_json = _build_weekly_execution_evaluation(
            record,
            target_row=matched,
            window_low=actual_window_low,
            window_high=actual_window_high,
        )

        await db.prediction_update_actual(
            record_id=record["id"],
            actual_close=float(matched.get("close", 0)),
            actual_low=matched.get("low"),
            actual_high=matched.get("high"),
            actual_window_low=actual_window_low,
            actual_window_high=actual_window_high,
            execution_json=execution_json,
        )
        evaluated_count += 1

    calibration_refreshed = False
    if evaluated_count > 0:
        from app.services import confidence_calibration_service

        await confidence_calibration_service.refresh_empirical_profiles()
        calibration_refreshed = True

    radar_result = {
        "updated_rows": 0,
        "evaluated_rows": 0,
        "partial_rows": 0,
        "fetch_errors": 0,
        "profile_status": "insufficient",
        "profile_sample_count": 0,
    }
    radar_error_count = 0
    try:
        radar_result = await opportunity_radar_lab_service.refresh_opportunity_radar_accuracy(limit=limit)
    except Exception:
        radar_error_count = 1

    return {
        "checked_at": datetime.now().isoformat(),
        "due_pending_count": len(pending),
        "evaluated_count": evaluated_count,
        "unmatched_count": unmatched_count,
        "error_count": error_count,
        "calibration_refreshed": calibration_refreshed,
        "radar_updated_rows": int(radar_result.get("updated_rows") or 0),
        "radar_evaluated_rows": int(radar_result.get("evaluated_rows") or 0),
        "radar_partial_rows": int(radar_result.get("partial_rows") or 0),
        "radar_fetch_errors": int(radar_result.get("fetch_errors") or 0),
        "radar_profile_status": radar_result.get("profile_status"),
        "radar_profile_sample_count": int(radar_result.get("profile_sample_count") or 0),
        "radar_error_count": radar_error_count,
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
