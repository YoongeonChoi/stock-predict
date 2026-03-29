"""Research and validation surfaces for forecast monitoring."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from app.analysis.next_day_forecast import MODEL_VERSION
from app.data import cache
from app.database import db
from app.services import (
    archive_service,
    confidence_calibration_service,
    learned_fusion_profile_service,
)

PREDICTION_LAB_CACHE_TTL_SECONDS = 180
PREDICTION_LAB_WAIT_TIMEOUT_SECONDS = 2.5
PREDICTION_LAB_BUILD_TIMEOUT_SECONDS = 8.0
PREDICTION_LAB_STATS_TIMEOUT_SECONDS = 2.0
PREDICTION_LAB_REFRESH_TIMEOUT_SECONDS = 8.0
PREDICTION_LAB_SAMPLE_WINDOW_MIN = 96
PREDICTION_LAB_SAMPLE_WINDOW_MAX = 180


def _prediction_label(prediction_type: str) -> str:
    if prediction_type == "next_day":
        return "1D"
    if prediction_type.endswith("5d"):
        return "5D"
    if prediction_type.endswith("20d"):
        return "20D"
    return prediction_type


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


def _parse_calibration_json(raw_snapshot: str | dict | None) -> dict:
    if raw_snapshot is None:
        return {}
    if isinstance(raw_snapshot, dict):
        return raw_snapshot
    if isinstance(raw_snapshot, str):
        try:
            parsed = json.loads(raw_snapshot)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


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
        calibration_snapshot = _parse_calibration_json(row.get("calibration_json"))
        fusion_metadata = calibration_snapshot.get("fusion_metadata") or {}
        graph_context = calibration_snapshot.get("graph_context") or {}

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
                "fusion_method": fusion_metadata.get("method") or "prior_only",
                "fusion_blend_weight": round(float(fusion_metadata.get("blend_weight") or 0.0), 4),
                "graph_context_used": bool(graph_context.get("used")),
                "graph_coverage": round(float(graph_context.get("coverage") or 0.0), 4),
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


def _normalize_empirical_calibration(rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for row in rows:
        prediction_type = str(row.get("prediction_type") or "")
        normalized.append(
            {
                "prediction_type": prediction_type,
                "label": _prediction_label(prediction_type),
                "method": row.get("method") or "empirical_sigmoid",
                "sample_count": int(row.get("sample_count") or 0),
                "positive_rate": round(float(row.get("positive_rate") or 0.0) * 100.0, 1),
                "brier_score": round(float(row.get("brier_score") or 0.0), 4),
                "prior_brier_score": round(float(row.get("prior_brier_score") or 0.0), 4),
                "max_reliability_gap": round(float(row.get("max_reliability_gap") or 0.0) * 100.0, 1),
                "reliability_bins": row.get("reliability_bins") or [],
                "fitted_at": row.get("fitted_at"),
            }
        )
    return normalized


def _summarize_fusion_rows(rows: list[dict]) -> dict:
    method_counts = {
        "prior_only": 0,
        "learned_blended": 0,
        "learned_blended_graph": 0,
    }
    graph_used_count = 0
    graph_coverages: list[float] = []
    graph_scores: list[float] = []
    blend_weights: list[float] = []
    peer_counts: list[float] = []
    parsed_count = 0

    for row in rows:
        calibration_snapshot = _parse_calibration_json(row.get("calibration_json"))
        if not calibration_snapshot:
            continue
        fusion_metadata = calibration_snapshot.get("fusion_metadata") or {}
        graph_context = calibration_snapshot.get("graph_context") or {}
        method = str(fusion_metadata.get("method") or "prior_only")
        if method not in method_counts:
            method = "prior_only"
        method_counts[method] += 1
        blend_weights.append(float(fusion_metadata.get("blend_weight") or 0.0))
        coverage = float(
            graph_context.get("coverage")
            or fusion_metadata.get("graph_coverage")
            or 0.0
        )
        graph_coverages.append(coverage)
        graph_scores.append(float(graph_context.get("graph_context_score") or 0.0))
        peer_counts.append(float(graph_context.get("peer_count") or 0.0))
        if bool(graph_context.get("used")):
            graph_used_count += 1
        parsed_count += 1

    current_method = max(method_counts, key=method_counts.get) if parsed_count else "prior_only"
    avg_blend_weight = sum(blend_weights) / len(blend_weights) if blend_weights else 0.0
    avg_graph_coverage = sum(graph_coverages) / len(graph_coverages) if graph_coverages else 0.0
    avg_graph_score = sum(graph_scores) / len(graph_scores) if graph_scores else 0.0
    avg_peer_count = sum(peer_counts) / len(peer_counts) if peer_counts else 0.0

    return {
        "record_count": parsed_count,
        "method_counts": method_counts,
        "current_method": current_method,
        "avg_blend_weight": round(avg_blend_weight, 4),
        "graph_context_used_rate": round(graph_used_count / parsed_count, 4) if parsed_count else 0.0,
        "avg_graph_coverage": round(avg_graph_coverage, 4),
        "avg_graph_score": round(avg_graph_score, 4),
        "avg_peer_count": round(avg_peer_count, 2),
        "graph_coverage_available": avg_graph_coverage > 0.0,
    }


def _normalize_horizon_accuracy(
    entries: list[tuple[str, str, dict, dict, dict | None]],
) -> list[dict]:
    rows: list[dict] = []
    for prediction_type, label, stats, fusion_summary, profile_summary in entries:
        profile_summary = profile_summary or {}
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
                "current_method": fusion_summary.get("current_method") or "prior_only",
                "fusion_profile_sample_count": int(profile_summary.get("sample_count") or 0),
                "avg_blend_weight": float(fusion_summary.get("avg_blend_weight") or 0.0),
                "graph_coverage": float(fusion_summary.get("avg_graph_coverage") or 0.0),
                "graph_context_used_rate": float(fusion_summary.get("graph_context_used_rate") or 0.0),
                "prior_brier_delta": profile_summary.get("prior_brier_delta"),
                "fusion_status": profile_summary.get("status") or "bootstrapping",
            }
        )
    return rows


def _build_graph_context_summary(
    per_horizon: list[dict],
) -> dict:
    total_records = sum(int(item.get("record_count") or 0) for item in per_horizon)
    if total_records <= 0:
        return {
            "coverage_available": False,
            "used_rate": 0.0,
            "avg_coverage": 0.0,
            "avg_score": 0.0,
            "avg_peer_count": 0.0,
            "records": 0,
            "by_horizon": [],
        }

    weighted = lambda key: round(
        sum(float(item.get(key) or 0.0) * int(item.get("record_count") or 0) for item in per_horizon)
        / total_records,
        4,
    )
    return {
        "coverage_available": any(bool(item.get("graph_coverage_available")) for item in per_horizon),
        "used_rate": weighted("graph_context_used_rate"),
        "avg_coverage": weighted("avg_graph_coverage"),
        "avg_score": weighted("avg_graph_score"),
        "avg_peer_count": weighted("avg_peer_count"),
        "records": total_records,
        "by_horizon": [
            {
                "prediction_type": item["prediction_type"],
                "label": item["label"],
                "used_rate": float(item.get("graph_context_used_rate") or 0.0),
                "avg_coverage": float(item.get("avg_graph_coverage") or 0.0),
                "avg_score": float(item.get("avg_graph_score") or 0.0),
                "avg_peer_count": float(item.get("avg_peer_count") or 0.0),
                "records": int(item.get("record_count") or 0),
            }
            for item in per_horizon
        ],
    }


def _build_fusion_status_summary(
    horizon_accuracy: list[dict],
    fusion_profiles: list[dict],
    graph_context_summary: dict,
) -> dict:
    profile_map = {row["prediction_type"]: row for row in fusion_profiles}
    last_refresh_time = learned_fusion_profile_service.get_last_refresh_time()
    method_mix = {
        "prior_only": sum(int(row.get("current_method") == "prior_only") for row in horizon_accuracy),
        "learned_blended": sum(int(row.get("current_method") == "learned_blended") for row in horizon_accuracy),
        "learned_blended_graph": sum(
            int(row.get("current_method") == "learned_blended_graph") for row in horizon_accuracy
        ),
    }
    return {
        "active_model_version": MODEL_VERSION,
        "last_refresh_time": last_refresh_time,
        "graph_coverage_available": bool(graph_context_summary.get("coverage_available")),
        "avg_blend_weight": round(
            sum(float(row.get("avg_blend_weight") or 0.0) for row in horizon_accuracy)
            / max(len(horizon_accuracy), 1),
            4,
        ),
        "method_mix": method_mix,
        "horizons": [
            {
                "prediction_type": row["prediction_type"],
                "label": row["label"],
                "current_method": row.get("current_method") or "prior_only",
                "profile_sample_count": int(profile_map.get(row["prediction_type"], {}).get("sample_count") or 0),
                "avg_blend_weight": float(row.get("avg_blend_weight") or 0.0),
                "graph_coverage": float(row.get("graph_coverage") or 0.0),
                "prior_brier_delta": profile_map.get(row["prediction_type"], {}).get("prior_brier_delta"),
                "status": profile_map.get(row["prediction_type"], {}).get("status") or "bootstrapping",
            }
            for row in horizon_accuracy
        ],
    }


def _build_insights(
    accuracy: dict,
    by_country: list[dict],
    calibration: list[dict],
    recent_records: list[dict],
    horizon_accuracy: list[dict],
    empirical_calibration: list[dict],
    fusion_profiles: list[dict],
    graph_context_summary: dict,
    fusion_status_summary: dict,
) -> list[str]:
    insights: list[str] = []
    total_predictions = int(accuracy.get("total_predictions", 0) or 0)
    direction_accuracy = float(accuracy.get("direction_accuracy", 0.0) or 0.0) * 100.0
    within_range_rate = float(accuracy.get("within_range_rate", 0.0) or 0.0) * 100.0
    avg_error_pct = float(accuracy.get("avg_error_pct", 0.0) or 0.0)

    if total_predictions == 0:
        return ["검증 완료 표본이 아직 많지 않아 예측 연구실은 실측 로그를 더 쌓는 단계에 있습니다."]

    insights.append(
        f"현재 검증 완료 표본 {total_predictions}건 기준으로 방향 적중률 {direction_accuracy:.1f}%, 평균 오차 {avg_error_pct:.2f}%를 기록하고 있습니다."
    )
    insights.append(
        f"예측 밴드는 실현 종가를 {within_range_rate:.1f}% 비율로 포함하고 있어, 점예측보다 분포 해석이 더 중요하다는 점을 보여 줍니다."
    )

    if by_country:
        best_country = min(by_country, key=lambda item: (-item["direction_accuracy"], item["avg_error_pct"]))
        insights.append(
            f"현재 가장 안정적인 시장은 {best_country['label']}이며, 방향 적중률 {best_country['direction_accuracy'] * 100:.1f}%와 평균 오차 {best_country['avg_error_pct']:.2f}%를 보입니다."
        )

    if calibration:
        strongest_bucket = max(calibration, key=lambda item: item.get("direction_accuracy", 0))
        insights.append(
            f"신뢰도 구간 {strongest_bucket['bucket']}은 방향 적중률 {strongest_bucket['direction_accuracy']:.1f}%로 현재 가장 안정적으로 작동합니다."
        )

    active_profiles = [row for row in fusion_profiles if row.get("status") == "active"]
    if active_profiles:
        best_profile = max(active_profiles, key=lambda item: float(item.get("prior_brier_delta") or 0.0))
        insights.append(
            f"{best_profile['label']} learned fusion은 표본 {best_profile['sample_count']}건에서 prior 대비 Brier {float(best_profile.get('prior_brier_delta') or 0.0):.4f}만큼 개선했습니다."
        )
    else:
        insights.append("learned fusion은 아직 bootstrap 단계라 prior backbone 중심으로 동작하고 있습니다.")

    if graph_context_summary.get("coverage_available"):
        insights.append(
            f"graph context는 최근 검증 로그의 {float(graph_context_summary.get('used_rate') or 0.0) * 100:.1f}%에서 사용됐고, 평균 coverage {float(graph_context_summary.get('avg_coverage') or 0.0):.2f}로 반영됐습니다."
        )

    misses = [record for record in recent_records if record.get("direction_hit") is False and record.get("abs_error_pct") is not None]
    if misses:
        worst = max(misses, key=lambda item: item["abs_error_pct"])
        insights.append(
            f"최근 가장 큰 실패 사례는 {worst['symbol']} ({worst['target_date']})이며, 기준가 대비 오차 {worst['abs_error_pct']:.2f}%였습니다."
        )

    if fusion_status_summary.get("last_refresh_time"):
        insights.append(
            f"learned fusion profile은 {fusion_status_summary['last_refresh_time']} 기준으로 갱신됐고, 현재 모델 버전은 {fusion_status_summary['active_model_version']}입니다."
        )

    return insights[:6]


def _zero_prediction_stats() -> dict:
    return {
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


async def _safe_prediction_stats(prediction_type: str) -> dict:
    try:
        return await asyncio.wait_for(
            db.prediction_stats(prediction_type),
            timeout=PREDICTION_LAB_STATS_TIMEOUT_SECONDS,
        )
    except Exception:
        return _zero_prediction_stats()


async def _build_prediction_lab_fallback(
    *,
    limit_recent: int,
    reason: str,
) -> dict:
    accuracy = await archive_service.get_accuracy(refresh=False)
    stats_5d, stats_20d = await asyncio.gather(
        _safe_prediction_stats("distributional_5d"),
        _safe_prediction_stats("distributional_20d"),
    )
    fusion_profiles = learned_fusion_profile_service.get_profile_summary()
    fusion_profile_map = {row["prediction_type"]: row for row in fusion_profiles}
    empirical_calibration = _normalize_empirical_calibration(
        confidence_calibration_service.get_profile_summary()
    )
    per_horizon_fusion = [
        {"prediction_type": "next_day", "label": "1D", **_summarize_fusion_rows([])},
        {"prediction_type": "distributional_5d", "label": "5D", **_summarize_fusion_rows([])},
        {"prediction_type": "distributional_20d", "label": "20D", **_summarize_fusion_rows([])},
    ]
    horizon_accuracy = _normalize_horizon_accuracy(
        [
            ("next_day", "1D", accuracy, per_horizon_fusion[0], fusion_profile_map.get("next_day")),
            ("distributional_5d", "5D", stats_5d, per_horizon_fusion[1], fusion_profile_map.get("distributional_5d")),
            ("distributional_20d", "20D", stats_20d, per_horizon_fusion[2], fusion_profile_map.get("distributional_20d")),
        ]
    )
    graph_context_summary = _build_graph_context_summary(per_horizon_fusion)
    fusion_status_summary = _build_fusion_status_summary(
        horizon_accuracy,
        fusion_profiles,
        graph_context_summary,
    )
    response = {
        "generated_at": datetime.now().isoformat(),
        "partial": True,
        "fallback_reason": reason,
        "accuracy": accuracy,
        "horizon_accuracy": horizon_accuracy,
        "empirical_calibration": empirical_calibration,
        "fusion_profiles": fusion_profiles,
        "graph_context_summary": graph_context_summary,
        "fusion_status_summary": fusion_status_summary,
        "breakdown": {
            "by_country": [],
            "by_scope": [],
            "by_model": [],
        },
        "calibration": [],
        "recent_trend": [],
        "recent_records": [],
        "insights": _build_insights(
            accuracy,
            [],
            [],
            [],
            horizon_accuracy,
            empirical_calibration,
            fusion_profiles,
            graph_context_summary,
            fusion_status_summary,
        ),
    }
    if not response["insights"]:
        response["insights"] = [
            f"실측 검증 상세 집계가 지연돼 최근 {min(limit_recent, 40)}건 테이블 대신 핵심 검증 스냅샷을 먼저 제공합니다."
        ]
    return response


async def _build_prediction_lab_payload(limit_recent: int, refresh: bool) -> dict:
    if refresh:
        await asyncio.wait_for(
            archive_service.refresh_prediction_accuracy(limit=200),
            timeout=PREDICTION_LAB_REFRESH_TIMEOUT_SECONDS,
        )

    sample_window = max(
        PREDICTION_LAB_SAMPLE_WINDOW_MIN,
        min(PREDICTION_LAB_SAMPLE_WINDOW_MAX, limit_recent * 3),
    )
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
        next_day_samples,
        distribution_5d_samples,
        distribution_20d_samples,
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
        db.prediction_evaluated_samples(prediction_type="next_day", limit=sample_window),
        db.prediction_evaluated_samples(prediction_type="distributional_5d", limit=sample_window),
        db.prediction_evaluated_samples(prediction_type="distributional_20d", limit=sample_window),
    )

    fusion_profiles = learned_fusion_profile_service.get_profile_summary()
    fusion_profile_map = {row["prediction_type"]: row for row in fusion_profiles}
    empirical_calibration = _normalize_empirical_calibration(
        confidence_calibration_service.get_profile_summary()
    )
    per_horizon_fusion = [
        {
            "prediction_type": "next_day",
            "label": "1D",
            **_summarize_fusion_rows(next_day_samples),
        },
        {
            "prediction_type": "distributional_5d",
            "label": "5D",
            **_summarize_fusion_rows(distribution_5d_samples),
        },
        {
            "prediction_type": "distributional_20d",
            "label": "20D",
            **_summarize_fusion_rows(distribution_20d_samples),
        },
    ]
    horizon_accuracy = _normalize_horizon_accuracy(
        [
            (
                "next_day",
                "1D",
                accuracy,
                per_horizon_fusion[0],
                fusion_profile_map.get("next_day"),
            ),
            (
                "distributional_5d",
                "5D",
                stats_5d,
                per_horizon_fusion[1],
                fusion_profile_map.get("distributional_5d"),
            ),
            (
                "distributional_20d",
                "20D",
                stats_20d,
                per_horizon_fusion[2],
                fusion_profile_map.get("distributional_20d"),
            ),
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
    graph_context_summary = _build_graph_context_summary(per_horizon_fusion)
    fusion_status_summary = _build_fusion_status_summary(
        horizon_accuracy,
        fusion_profiles,
        graph_context_summary,
    )

    response = {
        "generated_at": datetime.now().isoformat(),
        "partial": False,
        "fallback_reason": None,
        "accuracy": accuracy,
        "horizon_accuracy": horizon_accuracy,
        "empirical_calibration": empirical_calibration,
        "fusion_profiles": fusion_profiles,
        "graph_context_summary": graph_context_summary,
        "fusion_status_summary": fusion_status_summary,
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
            fusion_profiles,
            graph_context_summary,
            fusion_status_summary,
        ),
    }
    return response


async def get_prediction_lab(limit_recent: int = 40, refresh: bool = True) -> dict:
    cache_key = f"prediction_lab:v5:{limit_recent}:{int(refresh)}"

    async def _fetch_prediction_lab():
        try:
            return await asyncio.wait_for(
                _build_prediction_lab_payload(limit_recent, refresh),
                timeout=PREDICTION_LAB_BUILD_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return await _build_prediction_lab_fallback(
                limit_recent=limit_recent,
                reason="prediction_lab_timeout",
            )
        except Exception:
            return await _build_prediction_lab_fallback(
                limit_recent=limit_recent,
                reason="prediction_lab_error",
            )

    return await cache.get_or_fetch(
        cache_key,
        _fetch_prediction_lab,
        ttl=PREDICTION_LAB_CACHE_TTL_SECONDS,
        wait_timeout=PREDICTION_LAB_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: _build_prediction_lab_fallback(
            limit_recent=limit_recent,
            reason="prediction_lab_cache_wait_timeout",
        ),
    )
