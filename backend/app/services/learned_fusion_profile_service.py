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
_LAST_REFRESH_AT: str | None = None


def set_profiles(profiles: Mapping[str, LearnedFusionProfile] | None) -> None:
    _PROFILE_REGISTRY.clear()
    if profiles:
        _PROFILE_REGISTRY.update(dict(profiles))


def get_profiles() -> dict[str, LearnedFusionProfile]:
    return dict(_PROFILE_REGISTRY)


def get_profile(prediction_type: str) -> LearnedFusionProfile | None:
    return _PROFILE_REGISTRY.get(prediction_type)


def get_profile_for_horizon(horizon_days: int) -> LearnedFusionProfile | None:
    prediction_type = "next_day" if horizon_days <= 1 else "distributional_5d" if horizon_days <= 5 else "distributional_20d"
    return get_profile(prediction_type)


def get_last_refresh_time() -> str | None:
    return _LAST_REFRESH_AT


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


async def refresh_profiles(
    *,
    prediction_types: tuple[str, ...] = CALIBRATED_PREDICTION_TYPES,
    limit: int = MAX_FUSION_SAMPLES,
) -> dict[str, LearnedFusionProfile]:
    global _LAST_REFRESH_AT

    profiles: dict[str, LearnedFusionProfile] = {}
    for prediction_type in prediction_types:
        rows = await db.prediction_evaluated_samples(prediction_type=prediction_type, limit=limit)
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
    active_times = [profile.fitted_at for profile in profiles.values() if profile.fitted_at]
    _LAST_REFRESH_AT = max(active_times) if active_times else None
    return profiles
