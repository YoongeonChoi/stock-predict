from __future__ import annotations

import json
from datetime import datetime

import numpy as np

from app.database import db
from app.scoring.confidence import (
    CALIBRATION_FEATURE_NAMES,
    EmpiricalCalibrationProfile,
    build_bootstrap_prior,
    calibration_feature_vector,
    get_empirical_calibration_profiles,
    set_empirical_calibration_profiles,
)

CALIBRATED_PREDICTION_TYPES = ("next_day", "distributional_5d", "distributional_20d")
MAX_CALIBRATION_SAMPLES = 2500
MIN_CALIBRATION_SAMPLES = 24
MIN_CLASS_COUNT = 6


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _prediction_bucket(prediction_type: str) -> int:
    if prediction_type == "next_day":
        return 1
    if prediction_type.endswith("5d"):
        return 5
    return 20


def _direction_hit(row: dict) -> int | None:
    reference_price = float(row.get("reference_price") or 0.0)
    actual_close = row.get("actual_close")
    direction = str(row.get("direction") or "").lower()
    if reference_price <= 0 or actual_close is None or direction not in {"up", "down", "flat"}:
        return None
    actual_close = float(actual_close)
    if direction == "up":
        return 1 if actual_close > reference_price else 0
    if direction == "down":
        return 1 if actual_close < reference_price else 0
    return 1 if abs(actual_close - reference_price) / reference_price <= 0.001 else 0


def _build_dataset(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    features: list[list[float]] = []
    targets: list[float] = []
    for row in rows:
        hit = _direction_hit(row)
        if hit is None:
            continue
        raw_snapshot = row.get("calibration_json")
        if not raw_snapshot:
            continue
        try:
            snapshot = json.loads(raw_snapshot)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(snapshot, dict):
            continue
        features.append(calibration_feature_vector(snapshot))
        targets.append(float(hit))
    if not features:
        return np.empty((0, len(CALIBRATION_FEATURE_NAMES)), dtype=float), np.empty((0,), dtype=float)
    return np.array(features, dtype=float), np.array(targets, dtype=float)


def _brier_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_pred - y_true) ** 2)) if y_true.size else 0.0


def _fit_regularized_sigmoid(
    *,
    prediction_type: str,
    features: np.ndarray,
    targets: np.ndarray,
) -> EmpiricalCalibrationProfile | None:
    sample_count = int(targets.size)
    positive_count = int(float(np.sum(targets)))
    negative_count = sample_count - positive_count
    if sample_count < MIN_CALIBRATION_SAMPLES or min(positive_count, negative_count) < MIN_CLASS_COUNT:
        return None

    bucket = _prediction_bucket(prediction_type)
    prior_intercept, prior_weight_map = build_bootstrap_prior(bucket)
    prior_weights = np.array([prior_weight_map[name] for name in CALIBRATION_FEATURE_NAMES], dtype=float)

    intercept = float(prior_intercept)
    weights = prior_weights.copy()

    if sample_count < 60:
        l2_penalty = 18.0
    elif sample_count < 160:
        l2_penalty = 9.0
    else:
        l2_penalty = 4.0

    for step in range(420):
        logits = intercept + features @ weights
        probabilities = _sigmoid(logits)
        errors = probabilities - targets
        sample_scale = max(sample_count, 1)
        intercept_gradient = float(np.mean(errors)) + ((l2_penalty * 0.2) / sample_scale) * (intercept - prior_intercept)
        weight_gradient = (features.T @ errors) / sample_scale + (l2_penalty / sample_scale) * (weights - prior_weights)
        learning_rate = 0.22 / np.sqrt(step + 1)
        intercept -= learning_rate * intercept_gradient
        weights -= learning_rate * weight_gradient

    adaptation_strength = min(0.9, max(0.15, sample_count / 240.0))
    intercept = prior_intercept + adaptation_strength * (intercept - prior_intercept)
    weights = prior_weights + adaptation_strength * (weights - prior_weights)

    prior_probabilities = _sigmoid(prior_intercept + features @ prior_weights)
    fitted_probabilities = _sigmoid(intercept + features @ weights)
    prior_brier = _brier_score(targets, prior_probabilities)
    fitted_brier = _brier_score(targets, fitted_probabilities)

    if fitted_brier > prior_brier:
        soft_blend = adaptation_strength * 0.5
        intercept = prior_intercept + soft_blend * (intercept - prior_intercept)
        weights = prior_weights + soft_blend * (weights - prior_weights)
        fitted_probabilities = _sigmoid(intercept + features @ weights)
        fitted_brier = _brier_score(targets, fitted_probabilities)

    return EmpiricalCalibrationProfile(
        prediction_type=prediction_type,
        horizon_bucket=bucket,
        intercept=round(float(intercept), 6),
        feature_weights={
            feature_name: round(float(weight), 6)
            for feature_name, weight in zip(CALIBRATION_FEATURE_NAMES, weights)
        },
        sample_count=sample_count,
        positive_rate=round(positive_count / sample_count, 4),
        brier_score=round(fitted_brier, 6),
        prior_brier_score=round(prior_brier, 6),
        fitted_at=datetime.now().isoformat(),
        method=f"empirical_sigmoid_{bucket}d",
    )


async def refresh_empirical_profiles(
    *,
    prediction_types: tuple[str, ...] = CALIBRATED_PREDICTION_TYPES,
    limit: int = MAX_CALIBRATION_SAMPLES,
) -> dict[str, EmpiricalCalibrationProfile]:
    profiles: dict[str, EmpiricalCalibrationProfile] = {}
    for prediction_type in prediction_types:
        rows = await db.prediction_evaluated_samples(prediction_type=prediction_type, limit=limit)
        features, targets = _build_dataset(rows)
        profile = _fit_regularized_sigmoid(
            prediction_type=prediction_type,
            features=features,
            targets=targets,
        )
        if profile is not None:
            profiles[prediction_type] = profile
    set_empirical_calibration_profiles(profiles)
    return profiles


def get_profile_summary() -> list[dict]:
    profiles = get_empirical_calibration_profiles()
    summary = []
    for prediction_type in CALIBRATED_PREDICTION_TYPES:
        profile = profiles.get(prediction_type)
        if profile is None:
            continue
        summary.append(
            {
                "prediction_type": prediction_type,
                "method": profile.method,
                "sample_count": profile.sample_count,
                "positive_rate": profile.positive_rate,
                "brier_score": profile.brier_score,
                "prior_brier_score": profile.prior_brier_score,
                "fitted_at": profile.fitted_at,
            }
        )
    return summary
