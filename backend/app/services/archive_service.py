"""Report archiving and prediction accuracy tracking."""

import json
from datetime import datetime

from app.data import yfinance_client
from app.database import db


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
            model_version=next_day.get("model_version"),
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


async def refresh_prediction_accuracy(limit: int = 200):
    pending = await db.prediction_pending(datetime.now().date().isoformat(), limit=limit)
    for record in pending:
        try:
            prices = await yfinance_client.get_price_history(record["symbol"], period="1y")
        except Exception:
            continue

        matched = next((row for row in prices if row.get("date") == record["target_date"]), None)
        if not matched:
            continue

        await db.prediction_update_actual(
            record_id=record["id"],
            actual_close=float(matched.get("close", 0)),
            actual_low=matched.get("low"),
            actual_high=matched.get("high"),
        )


async def get_accuracy() -> dict:
    await refresh_prediction_accuracy()
    return await db.prediction_stats("next_day")
