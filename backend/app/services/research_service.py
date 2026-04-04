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
PREDICTION_LAB_RECENT_TIMEOUT_SECONDS = 1.5
PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS = 1.5


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
        prediction_type = str(row.get("prediction_type") or "next_day")
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
                "prediction_type": prediction_type,
                "prediction_label": _prediction_label(prediction_type),
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


def _runtime_summary_map() -> dict[str, dict]:
    return {
        row["prediction_type"]: row
        for row in learned_fusion_profile_service.get_runtime_summary()
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


def _severity_rank(level: str) -> int:
    if level == "high":
        return 0
    if level == "medium":
        return 1
    return 2


def _build_action_queue(
    *,
    accuracy: dict,
    horizon_accuracy: list[dict],
    empirical_calibration: list[dict],
    fusion_profiles: list[dict],
    graph_context_summary: dict,
    recent_records: list[dict],
) -> list[dict]:
    actions: list[dict] = []
    empirical_by_type = {row["prediction_type"]: row for row in empirical_calibration}
    fusion_by_type = {row["prediction_type"]: row for row in fusion_profiles}

    for row in horizon_accuracy:
        prediction_type = row["prediction_type"]
        label = row["label"]
        total_predictions = int(row.get("total_predictions") or 0)
        direction_accuracy = float(row.get("direction_accuracy") or 0.0) * 100.0
        avg_error_pct = float(row.get("avg_error_pct") or 0.0)
        profile = fusion_by_type.get(prediction_type) or {}
        empirical = empirical_by_type.get(prediction_type) or {}
        reliability_gap = float(empirical.get("max_reliability_gap") or 0.0)
        prior_brier_delta = profile.get("prior_brier_delta")

        if 0 < total_predictions < 30:
            actions.append(
                {
                    "key": f"{prediction_type}:sample",
                    "severity": "medium",
                    "title": f"{label} 검증 표본 축적 필요",
                    "detail": f"{label} 검증 완료 표본이 {total_predictions}건이라 방향 적중과 보정 상태를 단정하기엔 아직 얕습니다.",
                    "metric_label": "검증 표본",
                    "metric_value": f"{total_predictions}건",
                }
            )

        if reliability_gap >= 8.0:
            actions.append(
                {
                    "key": f"{prediction_type}:gap",
                    "severity": "high",
                    "title": f"{label} reliability gap 점검",
                    "detail": f"{label} calibrator의 최대 gap이 {reliability_gap:.1f}%로 커서 confidence 해석이 흔들릴 수 있습니다.",
                    "metric_label": "최대 gap",
                    "metric_value": f"{reliability_gap:.1f}%",
                }
            )

        if total_predictions >= 20 and prior_brier_delta is not None and float(prior_brier_delta) <= 0:
            actions.append(
                {
                    "key": f"{prediction_type}:fusion",
                    "severity": "high",
                    "title": f"{label} fusion 성능 재점검",
                    "detail": f"{label} learned fusion이 prior 대비 Brier 개선을 만들지 못해 현재 조합 가중치 점검이 필요합니다.",
                    "metric_label": "prior delta",
                    "metric_value": f"{float(prior_brier_delta):.4f}",
                }
            )

        if total_predictions >= 20 and direction_accuracy < 55.0 and avg_error_pct >= 2.5:
            actions.append(
                {
                    "key": f"{prediction_type}:accuracy",
                    "severity": "medium",
                    "title": f"{label} 방향/오차 동시 점검",
                    "detail": f"{label}는 방향 적중 {direction_accuracy:.1f}%에 평균 오차 {avg_error_pct:.2f}%로 최근 안정성이 약합니다.",
                    "metric_label": "방향 적중",
                    "metric_value": f"{direction_accuracy:.1f}%",
                }
            )

    if graph_context_summary.get("coverage_available"):
        graph_used_rate = float(graph_context_summary.get("used_rate") or 0.0) * 100.0
        avg_coverage = float(graph_context_summary.get("avg_coverage") or 0.0) * 100.0
        if graph_used_rate < 40.0:
            actions.append(
                {
                    "key": "graph:usage",
                    "severity": "medium",
                    "title": "Graph context 활용률 점검",
                    "detail": f"최근 검증 로그에서 graph context 사용률이 {graph_used_rate:.1f}%로 낮아, 관계형 보강이 충분히 쓰이지 못하고 있습니다.",
                    "metric_label": "활용률",
                    "metric_value": f"{graph_used_rate:.1f}%",
                }
            )
        elif avg_coverage < 35.0:
            actions.append(
                {
                    "key": "graph:coverage",
                    "severity": "medium",
                    "title": "Graph context coverage 보강",
                    "detail": f"graph context가 쓰이더라도 평균 coverage가 {avg_coverage:.1f}%라, peer/sector 관계 정보가 얕게 들어가고 있습니다.",
                    "metric_label": "평균 coverage",
                    "metric_value": f"{avg_coverage:.1f}%",
                }
            )

    high_confidence_misses = [
        record
        for record in recent_records
        if record.get("direction_hit") is False and float(record.get("confidence") or 0.0) >= 60.0
    ]
    if high_confidence_misses:
        avg_error = sum(float(record.get("abs_error_pct") or 0.0) for record in high_confidence_misses) / max(
            len(high_confidence_misses), 1
        )
        actions.append(
            {
                "key": "recent:high-confidence-miss",
                "severity": "high",
                "title": "고신뢰 미스 리뷰 필요",
                "detail": f"최근 고신뢰 미스가 {len(high_confidence_misses)}건 있어 confidence 표시와 실제 적중률의 간극을 다시 확인해야 합니다.",
                "metric_label": "평균 오차",
                "metric_value": f"{avg_error:.2f}%",
            }
        )

    total_predictions = int(accuracy.get("total_predictions") or 0)
    if not actions and total_predictions > 0:
        actions.append(
            {
                "key": "baseline:stable",
                "severity": "info",
                "title": "연구실 기본 점검 상태 유지",
                "detail": "현재 공개 검증 지표에서는 즉시 손봐야 할 큰 붕괴 신호가 없으므로, 최근 miss review와 horizon별 추세를 계속 확인하면 됩니다.",
                "metric_label": "검증 표본",
                "metric_value": f"{total_predictions}건",
            }
        )

    actions.sort(key=lambda item: (_severity_rank(item["severity"]), item["title"]))
    return actions[:4]


def _build_failure_patterns(recent_records: list[dict]) -> list[dict]:
    misses = [record for record in recent_records if record.get("direction_hit") is False]
    if not misses:
        return []

    patterns: list[dict] = []
    pattern_defs = [
        (
            "high_confidence_miss",
            "고신뢰 미스",
            lambda row: float(row.get("confidence") or 0.0) >= 60.0,
            "confidence가 높았는데도 방향이 빗나간 사례입니다.",
        ),
        (
            "range_miss",
            "밴드 이탈",
            lambda row: row.get("within_range") is False,
            "예측 밴드 밖으로 실제 종가가 벗어난 사례입니다.",
        ),
        (
            "prior_only_miss",
            "prior-only 미스",
            lambda row: (row.get("fusion_method") or "prior_only") == "prior_only",
            "fusion 보강 없이 prior backbone만으로 처리된 미스입니다.",
        ),
        (
            "graph_unused_miss",
            "graph 미사용 미스",
            lambda row: not bool(row.get("graph_context_used")),
            "graph context가 붙지 않은 상태에서 난 미스입니다.",
        ),
    ]

    for key, title, predicate, detail in pattern_defs:
        matched = [row for row in misses if predicate(row)]
        if not matched:
            continue
        avg_error_pct = sum(float(row.get("abs_error_pct") or 0.0) for row in matched) / max(len(matched), 1)
        patterns.append(
            {
                "key": key,
                "title": title,
                "detail": detail,
                "count": len(matched),
                "avg_error_pct": round(avg_error_pct, 2),
                "avg_confidence": round(
                    sum(float(row.get("confidence") or 0.0) for row in matched) / max(len(matched), 1),
                    1,
                ),
                "example_symbol": matched[0].get("symbol"),
                "severity": "high" if len(matched) >= 2 else "medium",
            }
        )

    patterns.sort(key=lambda item: (-item["count"], -item["avg_error_pct"], _severity_rank(item["severity"])))
    return patterns[:4]


def _build_review_queue(recent_records: list[dict]) -> list[dict]:
    if not recent_records:
        return []

    def _record_rank(row: dict) -> tuple[int, float, float]:
        miss_priority = 0 if row.get("direction_hit") is False else 1 if row.get("direction_hit") is True else 2
        confidence = float(row.get("confidence") or 0.0)
        abs_error_pct = float(row.get("abs_error_pct") or 0.0)
        return (miss_priority, -abs_error_pct, -confidence)

    queue: list[dict] = []
    for row in sorted(recent_records, key=_record_rank):
        direction_hit = row.get("direction_hit")
        within_range = row.get("within_range")
        symbol = row.get("symbol")
        prediction_label = _prediction_label(str(row.get("prediction_type") or "next_day"))
        if direction_hit is False:
            summary = (
                f"{prediction_label} 예측에서 {symbol} 방향 판단이 빗나갔고, "
                f"오차 {float(row.get('abs_error_pct') or 0.0):.2f}%를 기록했습니다."
            )
            review_kind = "miss"
        elif direction_hit is True and within_range is True:
            summary = f"{prediction_label} 예측에서 {symbol}은 방향과 밴드를 모두 맞췄습니다."
            review_kind = "clean-hit"
        elif direction_hit is True:
            summary = f"{prediction_label} 예측에서 {symbol}은 방향은 맞췄지만 밴드는 벗어났습니다."
            review_kind = "direction-hit"
        else:
            summary = f"{prediction_label} 예측에서 {symbol}은 아직 실제 종가 평가가 끝나지 않았습니다."
            review_kind = "pending"

        queue.append(
            {
                "id": row["id"],
                "prediction_type": row.get("prediction_type") or "next_day",
                "prediction_label": prediction_label,
                "scope": row["scope"],
                "symbol": symbol,
                "country_code": row.get("country_code"),
                "target_date": row["target_date"],
                "direction": row["direction"],
                "direction_hit": direction_hit,
                "within_range": within_range,
                "abs_error_pct": row.get("abs_error_pct"),
                "confidence": row["confidence"],
                "fusion_method": row.get("fusion_method") or "prior_only",
                "graph_context_used": bool(row.get("graph_context_used")),
                "graph_coverage": row.get("graph_coverage"),
                "review_kind": review_kind,
                "review_summary": summary,
                "stock_path": f"/stock/{symbol}" if row.get("scope") == "stock" and symbol else None,
            }
        )
    return queue[:6]


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


async def _safe_prediction_query(query, fallback, *, timeout: float):
    try:
        return await asyncio.wait_for(query(), timeout=timeout), None
    except Exception:
        return fallback, "timed_out"


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
    runtime_summary_map = _runtime_summary_map()
    empirical_calibration = _normalize_empirical_calibration(
        confidence_calibration_service.get_profile_summary()
    )
    horizon_accuracy = _normalize_horizon_accuracy(
        [
            ("next_day", "1D", accuracy, runtime_summary_map.get("next_day", {}), fusion_profile_map.get("next_day")),
            (
                "distributional_5d",
                "5D",
                stats_5d,
                runtime_summary_map.get("distributional_5d", {}),
                fusion_profile_map.get("distributional_5d"),
            ),
            (
                "distributional_20d",
                "20D",
                stats_20d,
                runtime_summary_map.get("distributional_20d", {}),
                fusion_profile_map.get("distributional_20d"),
            ),
        ]
    )
    graph_context_summary = _build_graph_context_summary(list(runtime_summary_map.values()))
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
        "action_queue": _build_action_queue(
            accuracy=accuracy,
            horizon_accuracy=horizon_accuracy,
            empirical_calibration=empirical_calibration,
            fusion_profiles=fusion_profiles,
            graph_context_summary=graph_context_summary,
            recent_records=[],
        ),
        "failure_patterns": [],
        "review_queue": [],
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

    fusion_profiles = learned_fusion_profile_service.get_profile_summary()
    fusion_profile_map = {row["prediction_type"]: row for row in fusion_profiles}
    runtime_summary_map = _runtime_summary_map()
    empirical_calibration = _normalize_empirical_calibration(
        confidence_calibration_service.get_profile_summary()
    )
    (
        accuracy_result,
        stats_5d_result,
        stats_20d_result,
        recent_rows_result,
        trend_rows_result,
        by_country_rows_result,
        by_scope_rows_result,
        by_model_rows_result,
        calibration_rows_result,
    ) = await asyncio.gather(
        _safe_prediction_query(lambda: db.prediction_stats("next_day"), _zero_prediction_stats(), timeout=PREDICTION_LAB_STATS_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_stats("distributional_5d"), _zero_prediction_stats(), timeout=PREDICTION_LAB_STATS_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_stats("distributional_20d"), _zero_prediction_stats(), timeout=PREDICTION_LAB_STATS_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_recent("next_day", limit_recent), [], timeout=PREDICTION_LAB_RECENT_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_daily_trend("next_day", 14), [], timeout=PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_country_breakdown("next_day", 10), [], timeout=PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_scope_breakdown("next_day", 10), [], timeout=PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_model_breakdown("next_day", 10), [], timeout=PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS),
        _safe_prediction_query(lambda: db.prediction_confidence_buckets("next_day"), [], timeout=PREDICTION_LAB_BREAKDOWN_TIMEOUT_SECONDS),
    )
    accuracy, accuracy_reason = accuracy_result
    stats_5d, stats_5d_reason = stats_5d_result
    stats_20d, stats_20d_reason = stats_20d_result
    recent_rows, recent_rows_reason = recent_rows_result
    trend_rows, trend_rows_reason = trend_rows_result
    by_country_rows, by_country_rows_reason = by_country_rows_result
    by_scope_rows, by_scope_rows_reason = by_scope_rows_result
    by_model_rows, by_model_rows_reason = by_model_rows_result
    calibration_rows, calibration_rows_reason = calibration_rows_result
    partial_reasons = [
        reason
        for reason in (
            accuracy_reason,
            stats_5d_reason,
            stats_20d_reason,
            recent_rows_reason,
            trend_rows_reason,
            by_country_rows_reason,
            by_scope_rows_reason,
            by_model_rows_reason,
            calibration_rows_reason,
        )
        if reason
    ]
    horizon_accuracy = _normalize_horizon_accuracy(
        [
            (
                "next_day",
                "1D",
                accuracy,
                runtime_summary_map.get("next_day", {}),
                fusion_profile_map.get("next_day"),
            ),
            (
                "distributional_5d",
                "5D",
                stats_5d,
                runtime_summary_map.get("distributional_5d", {}),
                fusion_profile_map.get("distributional_5d"),
            ),
            (
                "distributional_20d",
                "20D",
                stats_20d,
                runtime_summary_map.get("distributional_20d", {}),
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
    graph_context_summary = _build_graph_context_summary(list(runtime_summary_map.values()))
    fusion_status_summary = _build_fusion_status_summary(
        horizon_accuracy,
        fusion_profiles,
        graph_context_summary,
    )

    response = {
        "generated_at": datetime.now().isoformat(),
        "partial": bool(partial_reasons),
        "fallback_reason": "prediction_lab_partial_data" if partial_reasons else None,
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
        "action_queue": _build_action_queue(
            accuracy=accuracy,
            horizon_accuracy=horizon_accuracy,
            empirical_calibration=empirical_calibration,
            fusion_profiles=fusion_profiles,
            graph_context_summary=graph_context_summary,
            recent_records=recent_records,
        ),
        "failure_patterns": _build_failure_patterns(recent_records),
        "review_queue": _build_review_queue(recent_records),
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
    cache_key = f"prediction_lab:v6:{limit_recent}:{int(refresh)}"

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
