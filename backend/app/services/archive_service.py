"""Report archiving and prediction accuracy tracking."""

import json
from app.database import db


async def save_report(report_type: str, report: dict, country_code: str | None = None,
                      sector_id: str | None = None, ticker: str | None = None) -> int:
    scores = report.get("score")
    predictions = None
    if "forecast" in report:
        predictions = report["forecast"]
    elif "buy_sell_guide" in report:
        predictions = report["buy_sell_guide"]

    return await db.archive_save(
        report_type=report_type,
        report_json=report,
        country_code=country_code,
        sector_id=sector_id,
        ticker=ticker,
        scores_json=scores,
        predictions_json=predictions,
    )


async def list_reports(report_type: str | None = None,
                       country_code: str | None = None,
                       limit: int = 50) -> list[dict]:
    rows = await db.archive_list(report_type, country_code, limit)
    results = []
    for r in rows:
        preview = ""
        try:
            rj = json.loads(r.get("report_json", "{}"))
            preview = rj.get("market_summary", rj.get("summary", ""))[:200]
        except (json.JSONDecodeError, AttributeError):
            pass
        results.append({
            "id": r["id"],
            "report_type": r["report_type"],
            "country_code": r.get("country_code"),
            "sector_id": r.get("sector_id"),
            "ticker": r.get("ticker"),
            "created_at": r["created_at"],
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


async def get_accuracy() -> dict:
    return await db.accuracy_stats()
