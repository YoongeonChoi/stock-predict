"""Research and validation surfaces for forecast monitoring."""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.data import cache
from app.database import db
from app.services import archive_service, confidence_calibration_service


def _rate(hit_count: float | int | None, total: float | int | None) -> float:
    if not total:
        return 0.0
    return round(float(hit_count or 0) / float(total), 4)


def _normalize_breakdown(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        total = row.get("total") or 0
        normalized.append(
            {
                "label": row.get("label") or "N/A",
                "total": total,
                "direction_accuracy": _rate(row.get("direction_hits"), total),
                "within_range_rate": _rate(row.get("within_range"), total),
                "avg_error_pct": round(float((row.get("avg_abs_error") or 0) * 100.0), 2),
                "avg_confidence": round(float(row.get("avg_confidence") or 0), 2),
            }
        )
    return normalized


def _normalize_recent(rows: list[dict]) -> list[dict]:
    records = []
    for row in rows:
        actual_close = row.get("actual_close")
        reference_price = float(row.get("reference_price") or 0)
        predicted_close = float(row.get("predicted_close") or 0)
        direction = row.get("direction")
        direction_hit = None
        within_range = None
        abs_error_pct = None

        if actual_close is not None and reference_price:
            actual_close = float(actual_close)
            direction_hit = (
                (direction == "up" and actual_close > reference_price)
                or (direction == "down" and actual_close < reference_price)
                or (direction == "flat" and abs(actual_close - reference_price) / reference_price <= 0.001)
            )
            predicted_low = row.get("predicted_low")
            predicted_high = row.get("predicted_high")
            if predicted_low is not None and predicted_high is not None:
                within_range = float(predicted_low) <= actual_close <= float(predicted_high)
            abs_error_pct = round(abs(actual_close - predicted_close) / reference_price * 100.0, 2)

        records.append(
            {
                "id": row["id"],
                "scope": row["scope"],
                "symbol": row["symbol"],
                "country_code": row.get("country_code"),
                "target_date": row["target_date"],
                "reference_date": row.get("reference_date"),
                "reference_price": reference_price,
                "predicted_close": predicted_close,
                "predicted_low": row.get("predicted_low"),
                "predicted_high": row.get("predicted_high"),
                "actual_close": actual_close,
                "direction": direction,
                "direction_hit": direction_hit,
                "within_range": within_range,
                "abs_error_pct": abs_error_pct,
                "confidence": round(float(row.get("confidence") or 0), 2),
                "up_probability": round(float(row.get("up_probability") or 0), 2),
                "model_version": row.get("model_version") or "unknown",
                "created_at": row["created_at"],
                "evaluated_at": row.get("evaluated_at"),
            }
        )
    return records


def _normalize_trend(rows: list[dict]) -> list[dict]:
    trend = []
    for row in reversed(rows):
        evaluated_total = row.get("evaluated_total") or 0
        trend.append(
            {
                "target_date": row["target_date"],
                "total": row.get("total") or 0,
                "evaluated_total": evaluated_total,
                "direction_accuracy": _rate(row.get("direction_hits"), evaluated_total),
                "within_range_rate": _rate(row.get("within_range"), evaluated_total),
                "avg_error_pct": round(float((row.get("avg_abs_error") or 0) * 100.0), 2),
            }
        )
    return trend


def _normalize_horizon_accuracy(entries: list[tuple[str, str, dict]]) -> list[dict]:
    rows: list[dict] = []
    for prediction_type, label, stats in entries:
        rows.append(
            {
                "prediction_type": prediction_type,
                "label": label,
                "stored_predictions": stats.get("stored_predictions", 0),
                "pending_predictions": stats.get("pending_predictions", 0),
                "total_predictions": stats.get("total_predictions", 0),
                "direction_accuracy": stats.get("direction_accuracy", 0.0),
                "within_range_rate": stats.get("within_range_rate", 0.0),
                "avg_error_pct": stats.get("avg_error_pct", 0.0),
                "avg_confidence": stats.get("avg_confidence", 0.0),
            }
        )
    return rows


def _normalize_empirical_calibration(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        prediction_type = str(row.get("prediction_type") or "")
        label = "1D"
        if prediction_type.endswith("5d"):
            label = "5D"
        elif prediction_type.endswith("20d"):
            label = "20D"
        normalized.append(
            {
                "prediction_type": prediction_type,
                "label": label,
                "method": row.get("method") or "empirical_sigmoid",
                "sample_count": int(row.get("sample_count") or 0),
                "positive_rate": round(float(row.get("positive_rate") or 0.0) * 100.0, 1),
                "brier_score": round(float(row.get("brier_score") or 0.0), 4),
                "prior_brier_score": round(float(row.get("prior_brier_score") or 0.0), 4),
                "fitted_at": row.get("fitted_at"),
            }
        )
    return normalized


def _build_insights(
    accuracy: dict,
    by_country: list[dict],
    calibration: list[dict],
    recent_records: list[dict],
    horizon_accuracy: list[dict],
    empirical_calibration: list[dict],
) -> list[str]:
    insights: list[str] = []
    total_predictions = accuracy.get("total_predictions", 0)
    direction_accuracy = accuracy.get("direction_accuracy", 0) * 100.0
    within_range_rate = accuracy.get("within_range_rate", 0) * 100.0
    avg_error_pct = accuracy.get("avg_error_pct", 0)

    if total_predictions == 0:
        return ["Validated next-day predictions are still sparse, so the lab is ready but waiting for more observed outcomes."]

    insights.append(
        f"Validated next-day forecasts currently hit direction {direction_accuracy:.1f}% of the time with an average absolute error of {avg_error_pct:.2f}%."
    )
    insights.append(
        f"Prediction bands captured the realized close {within_range_rate:.1f}% of the time across {total_predictions} evaluated signals."
    )

    if by_country:
        best_country = min(by_country, key=lambda item: (-item["direction_accuracy"], item["avg_error_pct"]))
        insights.append(
            f"Best validated market so far is {best_country['label']} with {best_country['direction_accuracy'] * 100:.1f}% direction accuracy."
        )

    if calibration:
        strongest_bucket = max(calibration, key=lambda item: item.get("direction_accuracy", 0))
        insights.append(
            f"Confidence bucket {strongest_bucket['bucket']} is currently the most reliable, converting at {strongest_bucket['direction_accuracy']:.1f}% direction accuracy."
        )

    multi_horizon = [row for row in horizon_accuracy if row["prediction_type"] != "next_day" and row["total_predictions"] > 0]
    if multi_horizon:
        best_horizon = min(multi_horizon, key=lambda item: (-item["direction_accuracy"], item["avg_error_pct"]))
        insights.append(
            f"{best_horizon['label']} 분포 예측은 현재 방향 적중률 {best_horizon['direction_accuracy'] * 100:.1f}%로, 다중기간 calibrator가 실제 결과를 기준으로 다시 맞춰지고 있습니다."
        )

    if empirical_calibration:
        strongest_profile = max(empirical_calibration, key=lambda item: item.get("sample_count", 0))
        insights.append(
            f"{strongest_profile['label']} empirical calibrator는 {strongest_profile['sample_count']}건의 실측 로그를 사용 중이며 Brier score {strongest_profile['brier_score']:.4f}로 관리됩니다."
        )

    misses = [record for record in recent_records if record.get("direction_hit") is False and record.get("abs_error_pct") is not None]
    if misses:
        worst = max(misses, key=lambda item: item["abs_error_pct"])
        insights.append(
            f"Largest recent miss was {worst['symbol']} for {worst['target_date']}, where realized price diverged {worst['abs_error_pct']:.2f}% from the reference."
        )

    return insights[:5]


async def get_prediction_lab(limit_recent: int = 40, refresh: bool = True) -> dict:
    cache_key = f"prediction_lab:v2:{limit_recent}:{int(refresh)}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    if refresh:
        await archive_service.refresh_prediction_accuracy(limit=200)

    (
        accuracy,
        stats_5d,
        stats_20d,
        recent_rows,
        trend_rows,
        by_country_rows,
        by_scope_rows,
        by_model_rows,
        calibration_rows,
    ) = await asyncio.gather(
        db.prediction_stats("next_day"),
        db.prediction_stats("distributional_5d"),
        db.prediction_stats("distributional_20d"),
        db.prediction_recent("next_day", limit_recent),
        db.prediction_daily_trend("next_day", 14),
        db.prediction_country_breakdown("next_day", 10),
        db.prediction_scope_breakdown("next_day", 10),
        db.prediction_model_breakdown("next_day", 10),
        db.prediction_confidence_buckets("next_day"),
    )
    empirical_calibration = _normalize_empirical_calibration(confidence_calibration_service.get_profile_summary())
    horizon_accuracy = _normalize_horizon_accuracy(
        [
            ("next_day", "1D", accuracy),
            ("distributional_5d", "5D", stats_5d),
            ("distributional_20d", "20D", stats_20d),
        ]
    )

    recent_records = _normalize_recent(recent_rows)
    trend = _normalize_trend(trend_rows)
    by_country = _normalize_breakdown(by_country_rows)
    by_scope = _normalize_breakdown(by_scope_rows)
    by_model = _normalize_breakdown(by_model_rows)
    calibration = [
        {
            "bucket": row["bucket"],
            "total": row.get("total") or 0,
            "avg_confidence": round(float(row.get("avg_confidence") or 0), 2),
            "realized_up_rate": round(float(row.get("realized_up_rate") or 0), 2),
            "direction_accuracy": round(float(row.get("direction_accuracy") or 0), 2),
            "avg_error_pct": round(float(row.get("avg_error_pct") or 0), 2),
        }
        for row in calibration_rows
    ]

    response = {
        "generated_at": datetime.now().isoformat(),
        "accuracy": accuracy,
        "horizon_accuracy": horizon_accuracy,
        "empirical_calibration": empirical_calibration,
        "breakdown": {
            "by_country": by_country,
            "by_scope": by_scope,
            "by_model": by_model,
        },
        "calibration": calibration,
        "recent_trend": trend,
        "recent_records": recent_records,
        "insights": _build_insights(
            accuracy,
            by_country,
            calibration,
            recent_records,
            horizon_accuracy,
            empirical_calibration,
        ),
    }
    await cache.set(cache_key, response, 180)
    return response
