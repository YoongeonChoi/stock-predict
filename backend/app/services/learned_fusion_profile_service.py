from __future__ import annotations

import json
from typing import Mapping

from app.analysis.learned_fusion import (
    MIN_FUSION_SAMPLES,
    LearnedFusionProfile,
    fit_learned_fusion_profile,
)
from app.database import db

CALIBRATED_PREDICTION_TYPES = ("next_day", "distributional_5d", "distributional_20d")
MAX_FUSION_SAMPLES = 2500

_PROFILE_REGISTRY: dict[str, LearnedFusionProfile] = {}
_RUNTIME_SUMMARY_REGISTRY: dict[str, dict] = {}
_LAST_REFRESH_AT: str | None = None


def set_profiles(profiles: Mapping[str, LearnedFusionProfile] | None) -> None:
    _PROFILE_REGISTRY.clear()
    if profiles:
        _PROFILE_REGISTRY.update(dict(profiles))


def set_runtime_summaries(summaries: Mapping[str, dict] | None) -> None:
    _RUNTIME_SUMMARY_REGISTRY.clear()
    if summaries:
        _RUNTIME_SUMMARY_REGISTRY.update(dict(summaries))


def get_profiles() -> dict[str, LearnedFusionProfile]:
    return dict(_PROFILE_REGISTRY)


def get_profile(prediction_type: str) -> LearnedFusionProfile | None:
    return _PROFILE_REGISTRY.get(prediction_type)


def get_profile_for_horizon(horizon_days: int) -> LearnedFusionProfile | None:
    prediction_type = "next_day" if horizon_days <= 1 else "distributional_5d" if horizon_days <= 5 else "distributional_20d"
    return get_profile(prediction_type)


def get_last_refresh_time() -> str | None:
    return _LAST_REFRESH_AT


def get_runtime_summary() -> list[dict]:
    rows: list[dict] = []
    for prediction_type in CALIBRATED_PREDICTION_TYPES:
        profile = _PROFILE_REGISTRY.get(prediction_type)
        summary = _RUNTIME_SUMMARY_REGISTRY.get(prediction_type, {})
        label = "1D" if prediction_type == "next_day" else "5D" if prediction_type.endswith("5d") else "20D"
        current_method = str(summary.get("current_method") or (profile.method if profile else "prior_only"))
        rows.append(
            {
                "prediction_type": prediction_type,
                "label": label,
                "current_method": current_method,
                "record_count": int(summary.get("record_count") or 0),
                "avg_blend_weight": round(float(summary.get("avg_blend_weight") or 0.0), 4),
                "graph_context_used_rate": round(float(summary.get("graph_context_used_rate") or 0.0), 4),
                "avg_graph_coverage": round(float(summary.get("avg_graph_coverage") or 0.0), 4),
                "avg_graph_score": round(float(summary.get("avg_graph_score") or 0.0), 4),
                "avg_peer_count": round(float(summary.get("avg_peer_count") or 0.0), 2),
                "graph_coverage_available": bool(summary.get("graph_coverage_available")),
                "method_counts": summary.get("method_counts")
                or {
                    "prior_only": int(current_method == "prior_only"),
                    "learned_blended": int(current_method == "learned_blended"),
                    "learned_blended_graph": int(current_method == "learned_blended_graph"),
                },
            }
        )
    return rows


def get_profile_summary() -> list[dict]:
    rows: list[dict] = []
    for prediction_type in CALIBRATED_PREDICTION_TYPES:
        profile = _PROFILE_REGISTRY.get(prediction_type)
        if profile is None:
            label = "1D" if prediction_type == "next_day" else "5D" if prediction_type.endswith("5d") else "20D"
            rows.append(
                {
                    "prediction_type": prediction_type,
                    "label": label,
                    "method": "prior_only",
                    "sample_count": 0,
                    "positive_rate": 0.0,
                    "brier_score": None,
                    "prior_brier_score": None,
                    "prior_brier_delta": None,
                    "fitted_at": None,
                    "profile_bucket": "default",
                    "status": "bootstrapping",
                }
            )
            continue
        label = "1D" if profile.horizon_days == 1 else "5D" if profile.horizon_days == 5 else "20D"
        rows.append(
            {
                "prediction_type": profile.prediction_type,
                "label": label,
                "method": profile.method,
                "sample_count": profile.sample_count,
                "positive_rate": round(profile.positive_rate * 100.0, 1),
                "brier_score": round(profile.brier_score, 4),
                "prior_brier_score": round(profile.prior_brier_score, 4),
                "prior_brier_delta": round(profile.prior_brier_score - profile.brier_score, 4),
                "fitted_at": profile.fitted_at,
                "profile_bucket": profile.profile_bucket,
                "status": "active" if profile.sample_count >= MIN_FUSION_SAMPLES else "bootstrapping",
            }
        )
    return rows


def _parse_fusion_features(raw_snapshot: str | dict | None) -> dict | None:
    if raw_snapshot is None:
        return None
    snapshot = raw_snapshot
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except (TypeError, json.JSONDecodeError):
            return None
    if not isinstance(snapshot, dict):
        return None
    fusion_features = snapshot.get("fusion_features")
    if not isinstance(fusion_features, dict):
        return None
    return fusion_features


def _parse_calibration_snapshot(raw_snapshot: str | dict | None) -> dict:
    if raw_snapshot is None:
        return {}
    snapshot = raw_snapshot
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except (TypeError, json.JSONDecodeError):
            return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _summarize_runtime_rows(rows: list[dict]) -> dict:
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
        calibration_snapshot = _parse_calibration_snapshot(row.get("calibration_json"))
        fusion_metadata = calibration_snapshot.get("fusion_metadata") or {}
        graph_context = calibration_snapshot.get("graph_context") or {}
        if not fusion_metadata and not graph_context:
            continue
        method = str(fusion_metadata.get("method") or "prior_only")
        if method not in method_counts:
            method = "prior_only"
        method_counts[method] += 1
        blend_weights.append(float(fusion_metadata.get("blend_weight") or 0.0))
        graph_coverages.append(float(graph_context.get("coverage") or 0.0))
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
        "avg_blend_weight": avg_blend_weight,
        "graph_context_used_rate": (graph_used_count / parsed_count) if parsed_count else 0.0,
        "avg_graph_coverage": avg_graph_coverage,
        "avg_graph_score": avg_graph_score,
        "avg_peer_count": avg_peer_count,
        "graph_coverage_available": avg_graph_coverage > 0.0,
    }


async def refresh_profiles(
    *,
    prediction_types: tuple[str, ...] = CALIBRATED_PREDICTION_TYPES,
    limit: int = MAX_FUSION_SAMPLES,
) -> dict[str, LearnedFusionProfile]:
    global _LAST_REFRESH_AT

    profiles: dict[str, LearnedFusionProfile] = {}
    runtime_summaries: dict[str, dict] = {}
    for prediction_type in prediction_types:
        rows = await db.prediction_evaluated_samples(prediction_type=prediction_type, limit=limit)
        runtime_summaries[prediction_type] = _summarize_runtime_rows(rows)
        feature_rows: list[dict] = []
        reference_prices: list[float | None] = []
        actual_closes: list[float | None] = []
        for row in rows:
            fusion_features = _parse_fusion_features(row.get("calibration_json"))
            if not fusion_features:
                continue
            feature_rows.append(fusion_features)
            reference_prices.append(row.get("reference_price"))
            actual_closes.append(row.get("actual_close"))
        profile = fit_learned_fusion_profile(
            prediction_type=prediction_type,
            feature_rows=feature_rows,
            reference_prices=reference_prices,
            actual_closes=actual_closes,
        )
        if profile is not None:
            profiles[prediction_type] = profile

    set_profiles(profiles)
    set_runtime_summaries(runtime_summaries)
    active_times = [profile.fitted_at for profile in profiles.values() if profile.fitted_at]
    _LAST_REFRESH_AT = max(active_times) if active_times else None
    return profiles
