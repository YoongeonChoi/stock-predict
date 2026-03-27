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
MIN_ISOTONIC_SAMPLES = 120
MIN_ISOTONIC_CLASS_COUNT = 20
MIN_ISOTONIC_UNIQUE_PROBABILITIES = 4
RELIABILITY_BIN_COUNT = 5
ISOTONIC_BRIER_MARGIN = 0.00025
ISOTONIC_GAP_IMPROVEMENT = 0.03


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


def _build_reliability_bins(
    targets: np.ndarray,
    probabilities: np.ndarray,
    *,
    bin_count: int = RELIABILITY_BIN_COUNT,
) -> list[dict]:
    if targets.size == 0:
        return []

    bins: list[dict] = []
    edges = np.linspace(0.0, 1.0, bin_count + 1)
    for index in range(bin_count):
        lower = float(edges[index])
        upper = float(edges[index + 1])
        if index == bin_count - 1:
            mask = (probabilities >= lower) & (probabilities <= upper)
        else:
            mask = (probabilities >= lower) & (probabilities < upper)
        if not np.any(mask):
            continue
        bin_targets = targets[mask]
        bin_probabilities = probabilities[mask]
        predicted_mean = float(np.mean(bin_probabilities))
        empirical_rate = float(np.mean(bin_targets))
        gap = abs(predicted_mean - empirical_rate)
        bins.append(
            {
                "lower": round(lower, 4),
                "upper": round(upper, 4),
                "sample_count": int(bin_targets.size),
                "predicted_mean": round(predicted_mean, 4),
                "empirical_rate": round(empirical_rate, 4),
                "gap": round(gap, 4),
            }
        )
    return bins


def _max_reliability_gap(reliability_bins: list[dict]) -> float:
    if not reliability_bins:
        return 0.0
    return max(float(item.get("gap") or 0.0) for item in reliability_bins)


def _fit_isotonic_curve(probabilities: np.ndarray, targets: np.ndarray) -> tuple[list[float], list[float]] | None:
    if probabilities.size == 0:
        return None

    order = np.argsort(probabilities, kind="mergesort")
    sorted_probabilities = probabilities[order]
    sorted_targets = targets[order]

    blocks: list[dict[str, float | int]] = []
    for probability, target in zip(sorted_probabilities, sorted_targets):
        blocks.append(
            {
                "sum_targets": float(target),
                "count": 1,
                "avg_target": float(target),
                "max_probability": float(probability),
            }
        )
        while len(blocks) >= 2 and float(blocks[-2]["avg_target"]) > float(blocks[-1]["avg_target"]):
            right = blocks.pop()
            left = blocks.pop()
            merged_count = int(left["count"]) + int(right["count"])
            merged_sum = float(left["sum_targets"]) + float(right["sum_targets"])
            blocks.append(
                {
                    "sum_targets": merged_sum,
                    "count": merged_count,
                    "avg_target": merged_sum / merged_count,
                    "max_probability": float(right["max_probability"]),
                }
            )

    compressed_blocks: list[dict[str, float | int]] = []
    for block in blocks:
        avg_target = float(block["avg_target"])
        max_probability = float(block["max_probability"])
        if compressed_blocks and np.isclose(float(compressed_blocks[-1]["avg_target"]), avg_target, atol=1e-12):
            compressed_blocks[-1]["count"] = int(compressed_blocks[-1]["count"]) + int(block["count"])
            compressed_blocks[-1]["sum_targets"] = float(compressed_blocks[-1]["sum_targets"]) + float(block["sum_targets"])
            compressed_blocks[-1]["max_probability"] = max_probability
            continue
        compressed_blocks.append(
            {
                "sum_targets": float(block["sum_targets"]),
                "count": int(block["count"]),
                "avg_target": avg_target,
                "max_probability": max_probability,
            }
        )

    thresholds = [float(block["max_probability"]) for block in compressed_blocks]
    values = [float(np.clip(float(block["avg_target"]), 0.0, 1.0)) for block in compressed_blocks]
    if len(thresholds) != len(values) or not thresholds:
        return None
    return thresholds, values


def _apply_isotonic_curve(probabilities: np.ndarray, thresholds: list[float], values: list[float]) -> np.ndarray:
    calibrated = np.empty_like(probabilities)
    for index, probability in enumerate(probabilities):
        mapped = float(values[-1])
        for threshold, candidate in zip(thresholds, values):
            if float(probability) <= float(threshold):
                mapped = float(candidate)
                break
        calibrated[index] = mapped
    return calibrated


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

    sigmoid_reliability_bins = _build_reliability_bins(targets, fitted_probabilities)
    sigmoid_max_reliability_gap = _max_reliability_gap(sigmoid_reliability_bins)

    final_method = f"empirical_sigmoid_{bucket}d"
    final_probabilities = fitted_probabilities
    isotonic_thresholds: list[float] | None = None
    isotonic_values: list[float] | None = None
    reliability_bins = sigmoid_reliability_bins
    max_reliability_gap = sigmoid_max_reliability_gap

    unique_probability_count = int(np.unique(np.round(fitted_probabilities, 4)).size)
    if (
        sample_count >= MIN_ISOTONIC_SAMPLES
        and min(positive_count, negative_count) >= MIN_ISOTONIC_CLASS_COUNT
        and unique_probability_count >= MIN_ISOTONIC_UNIQUE_PROBABILITIES
    ):
        isotonic_curve = _fit_isotonic_curve(fitted_probabilities, targets)
        if isotonic_curve is not None:
            candidate_thresholds, candidate_values = isotonic_curve
            isotonic_probabilities = _apply_isotonic_curve(
                fitted_probabilities,
                candidate_thresholds,
                candidate_values,
            )
            isotonic_brier = _brier_score(targets, isotonic_probabilities)
            isotonic_reliability_bins = _build_reliability_bins(targets, isotonic_probabilities)
            isotonic_max_reliability_gap = _max_reliability_gap(isotonic_reliability_bins)
            brier_not_worse = isotonic_brier <= fitted_brier + ISOTONIC_BRIER_MARGIN
            gap_improved = isotonic_max_reliability_gap <= sigmoid_max_reliability_gap - ISOTONIC_GAP_IMPROVEMENT
            brier_improved = isotonic_brier <= fitted_brier - ISOTONIC_BRIER_MARGIN
            if brier_improved or (brier_not_worse and gap_improved):
                final_method = f"empirical_isotonic_{bucket}d"
                final_probabilities = isotonic_probabilities
                fitted_brier = isotonic_brier
                isotonic_thresholds = candidate_thresholds
                isotonic_values = candidate_values
                reliability_bins = isotonic_reliability_bins
                max_reliability_gap = isotonic_max_reliability_gap

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
        method=final_method,
        isotonic_thresholds=isotonic_thresholds,
        isotonic_values=isotonic_values,
        reliability_bins=reliability_bins,
        max_reliability_gap=round(max_reliability_gap, 6),
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
                "max_reliability_gap": profile.max_reliability_gap,
                "reliability_bins": profile.reliability_bins or [],
                "fitted_at": profile.fitted_at,
            }
        )
    return summary
