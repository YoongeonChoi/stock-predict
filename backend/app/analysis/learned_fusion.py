from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import tanh
from typing import Mapping

import numpy as np

from app.scoring.confidence import build_data_quality_support

MIN_FUSION_SAMPLES = 36
MIN_DIRECTION_CLASS_COUNT = 8
MAX_BLEND_WEIGHT = 0.65
FUSION_FEATURE_NAMES: tuple[str, ...] = (
    "prior_fused_score",
    "fundamental_score",
    "macro_score",
    "event_sentiment",
    "event_surprise",
    "event_uncertainty",
    "flow_score",
    "coverage_naver",
    "coverage_opendart",
    "regime_spread",
)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _direction_target(reference_price: float | None, actual_close: float | None) -> float | None:
    if reference_price is None or actual_close is None:
        return None
    reference = float(reference_price)
    actual = float(actual_close)
    if reference <= 0:
        return None
    if actual > reference:
        return 1.0
    if actual < reference:
        return 0.0
    return 0.5


def build_fusion_feature_map(
    *,
    prior_fused_score: float,
    fundamental_score: float,
    macro_score: float,
    event_sentiment: float,
    event_surprise: float,
    event_uncertainty: float,
    flow_score: float,
    coverage_naver: float,
    coverage_opendart: float,
    regime_spread: float,
) -> dict[str, float]:
    return {
        "prior_fused_score": round(float(prior_fused_score), 6),
        "fundamental_score": round(float(fundamental_score), 6),
        "macro_score": round(float(macro_score), 6),
        "event_sentiment": round(float(event_sentiment), 6),
        "event_surprise": round(float(event_surprise), 6),
        "event_uncertainty": round(float(event_uncertainty), 6),
        "flow_score": round(float(flow_score), 6),
        "coverage_naver": round(_clip(float(coverage_naver), 0.0, 1.0), 6),
        "coverage_opendart": round(_clip(float(coverage_opendart), 0.0, 1.0), 6),
        "regime_spread": round(_clip(float(regime_spread), -1.0, 1.0), 6),
    }


def fusion_feature_vector(snapshot: Mapping[str, float | int | bool | str | None]) -> list[float]:
    vector: list[float] = []
    for feature_name in FUSION_FEATURE_NAMES:
        value = snapshot.get(feature_name, 0.0)
        try:
            numeric = float(value or 0.0)
        except (TypeError, ValueError):
            numeric = 0.0
        if not np.isfinite(numeric):
            numeric = 0.0
        if feature_name in {"coverage_naver", "coverage_opendart", "event_uncertainty"}:
            numeric = _clip(numeric, 0.0, 1.0)
        elif feature_name == "regime_spread":
            numeric = _clip(numeric, -1.0, 1.0)
        else:
            numeric = _clip(numeric, -2.0, 2.0)
        vector.append(numeric)
    return vector


@dataclass(slots=True)
class LearnedFusionProfile:
    prediction_type: str
    horizon_days: int
    intercept: float
    feature_weights: dict[str, float]
    sample_count: int
    positive_rate: float
    brier_score: float
    prior_brier_score: float
    fitted_at: str
    profile_bucket: str = "default"
    method: str = "l2_logistic"


@dataclass(slots=True)
class LearnedFusionResult:
    fused_score: float
    learned_score: float
    learned_probability: float
    method: str
    sample_count: int
    blend_weight: float
    profile_fitted_at: str | None
    graph_context_used: bool
    graph_context_score: float
    graph_coverage: float


def _prediction_type_to_horizon(prediction_type: str) -> int:
    if prediction_type == "next_day":
        return 1
    if prediction_type.endswith("5d"):
        return 5
    return 20


def _build_prior_profile(prediction_type: str) -> tuple[float, np.ndarray]:
    horizon = _prediction_type_to_horizon(prediction_type)
    intercept = 0.0
    weights = np.zeros(len(FUSION_FEATURE_NAMES), dtype=float)
    weights[FUSION_FEATURE_NAMES.index("prior_fused_score")] = 1.35 if horizon == 1 else 1.22 if horizon == 5 else 1.08
    weights[FUSION_FEATURE_NAMES.index("fundamental_score")] = 0.22
    weights[FUSION_FEATURE_NAMES.index("macro_score")] = 0.18
    weights[FUSION_FEATURE_NAMES.index("event_sentiment")] = 0.14
    weights[FUSION_FEATURE_NAMES.index("event_surprise")] = 0.12
    weights[FUSION_FEATURE_NAMES.index("event_uncertainty")] = -0.18
    weights[FUSION_FEATURE_NAMES.index("flow_score")] = 0.09
    weights[FUSION_FEATURE_NAMES.index("coverage_naver")] = 0.06
    weights[FUSION_FEATURE_NAMES.index("coverage_opendart")] = 0.08
    weights[FUSION_FEATURE_NAMES.index("regime_spread")] = 0.15
    return intercept, weights


def _brier_score(targets: np.ndarray, probabilities: np.ndarray) -> float:
    return float(np.mean((targets - probabilities) ** 2)) if targets.size else 0.0


def fit_learned_fusion_profile(
    *,
    prediction_type: str,
    feature_rows: list[Mapping[str, float | int | bool | str | None]],
    reference_prices: list[float | None],
    actual_closes: list[float | None],
) -> LearnedFusionProfile | None:
    vectors: list[list[float]] = []
    targets: list[float] = []
    for feature_row, reference_price, actual_close in zip(feature_rows, reference_prices, actual_closes):
        target = _direction_target(reference_price, actual_close)
        if target is None:
            continue
        vectors.append(fusion_feature_vector(feature_row))
        targets.append(target)

    if not vectors:
        return None

    features = np.array(vectors, dtype=float)
    target_array = np.array(targets, dtype=float)
    binary_targets = np.where(target_array >= 0.5, 1.0, 0.0)
    sample_count = int(binary_targets.size)
    positive_count = int(np.sum(binary_targets))
    negative_count = sample_count - positive_count
    if sample_count < MIN_FUSION_SAMPLES or min(positive_count, negative_count) < MIN_DIRECTION_CLASS_COUNT:
        return None

    prior_intercept, prior_weights = _build_prior_profile(prediction_type)
    intercept = float(prior_intercept)
    weights = prior_weights.copy()
    sample_scale = max(sample_count, 1)
    if sample_count < 80:
        l2_penalty = 16.0
    elif sample_count < 160:
        l2_penalty = 8.0
    else:
        l2_penalty = 4.0

    for step in range(400):
        logits = intercept + features @ weights
        probabilities = _sigmoid(logits)
        errors = probabilities - binary_targets
        intercept_grad = float(np.mean(errors)) + ((l2_penalty * 0.15) / sample_scale) * (intercept - prior_intercept)
        weight_grad = (features.T @ errors) / sample_scale + (l2_penalty / sample_scale) * (weights - prior_weights)
        lr = 0.2 / np.sqrt(step + 1)
        intercept -= lr * intercept_grad
        weights -= lr * weight_grad

    adaptation = _clip(sample_count / 180.0, 0.18, 0.92)
    intercept = prior_intercept + adaptation * (intercept - prior_intercept)
    weights = prior_weights + adaptation * (weights - prior_weights)

    prior_probabilities = _sigmoid(prior_intercept + features @ prior_weights)
    fitted_probabilities = _sigmoid(intercept + features @ weights)
    prior_brier = _brier_score(binary_targets, prior_probabilities)
    fitted_brier = _brier_score(binary_targets, fitted_probabilities)
    if fitted_brier > prior_brier:
        soft_adaptation = adaptation * 0.5
        intercept = prior_intercept + soft_adaptation * (intercept - prior_intercept)
        weights = prior_weights + soft_adaptation * (weights - prior_weights)
        fitted_probabilities = _sigmoid(intercept + features @ weights)
        fitted_brier = _brier_score(binary_targets, fitted_probabilities)

    return LearnedFusionProfile(
        prediction_type=prediction_type,
        horizon_days=_prediction_type_to_horizon(prediction_type),
        intercept=round(float(intercept), 6),
        feature_weights={
            name: round(float(weight), 6)
            for name, weight in zip(FUSION_FEATURE_NAMES, weights)
        },
        sample_count=sample_count,
        positive_rate=round(positive_count / sample_count, 4),
        brier_score=round(fitted_brier, 6),
        prior_brier_score=round(prior_brier, 6),
        fitted_at=datetime.now().isoformat(),
    )


def apply_learned_fusion(
    *,
    horizon_days: int,
    prior_fused_score: float,
    feature_map: Mapping[str, float | int | bool | str | None],
    profile: LearnedFusionProfile | None,
    graph_context: Mapping[str, float | int | bool | str | None] | None,
    history_bars: int,
    macro_available: bool,
    fundamental_available: bool,
    flow_available: bool,
    event_count: int,
    event_uncertainty: float,
) -> LearnedFusionResult:
    graph_context = graph_context or {}
    graph_used = bool(graph_context.get("used"))
    graph_score = _clip(float(graph_context.get("graph_context_score") or 0.0), -1.0, 1.0)
    graph_coverage = _clip(float(graph_context.get("coverage") or 0.0), 0.0, 1.0)

    if profile is None or profile.sample_count < MIN_FUSION_SAMPLES:
        return LearnedFusionResult(
            fused_score=round(float(prior_fused_score), 6),
            learned_score=round(float(prior_fused_score), 6),
            learned_probability=round(float(_clip(0.5 + tanh(prior_fused_score) * 0.25, 0.0, 1.0)), 6),
            method="prior_only",
            sample_count=int(profile.sample_count if profile else 0),
            blend_weight=0.0,
            profile_fitted_at=profile.fitted_at if profile else None,
            graph_context_used=graph_used,
            graph_context_score=round(graph_score, 6),
            graph_coverage=round(graph_coverage, 6),
        )

    weights = np.array(
        [float(profile.feature_weights.get(name, 0.0)) for name in FUSION_FEATURE_NAMES],
        dtype=float,
    )
    vector = np.array(fusion_feature_vector(feature_map), dtype=float)
    learned_probability = float(_sigmoid(np.array([profile.intercept + vector @ weights], dtype=float))[0])
    learned_score = _clip((learned_probability - 0.5) * 2.4, -1.5, 1.5)
    if graph_used:
        learned_score = _clip(learned_score + graph_score * 0.22 * max(0.35, graph_coverage), -1.5, 1.5)

    data_quality_support = build_data_quality_support(
        history_bars=history_bars,
        macro_available=macro_available,
        fundamental_available=fundamental_available,
        flow_available=flow_available,
        event_count=event_count,
        event_uncertainty=event_uncertainty,
    )
    blend_weight = (
        _clip((profile.sample_count - 24) / 120.0, 0.0, MAX_BLEND_WEIGHT)
        * data_quality_support
        * max(0.35, graph_coverage)
    )
    fused_score = (float(prior_fused_score) * (1.0 - blend_weight)) + (learned_score * blend_weight)
    method = "learned_blended_graph" if graph_used else "learned_blended"
    return LearnedFusionResult(
        fused_score=round(float(fused_score), 6),
        learned_score=round(float(learned_score), 6),
        learned_probability=round(float(learned_probability), 6),
        method=method,
        sample_count=profile.sample_count,
        blend_weight=round(float(blend_weight), 6),
        profile_fitted_at=profile.fitted_at,
        graph_context_used=graph_used,
        graph_context_score=round(graph_score, 6),
        graph_coverage=round(graph_coverage, 6),
    )
