from __future__ import annotations

from dataclasses import dataclass
from math import exp


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + exp(-value))
    numerator = exp(value)
    return numerator / (1.0 + numerator)


def _normalize_support(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if numeric > 1.0:
        numeric /= 100.0
    return _clip(numeric, 0.0, 1.0)


def regime_alignment_score(
    *,
    regime_tailwind: str | None = None,
    market_stance: str | None = None,
) -> float:
    if regime_tailwind == "tailwind" or market_stance == "risk_on":
        return 1.0
    if regime_tailwind == "headwind" or market_stance == "risk_off":
        return 0.18
    return 0.55


def action_tiebreak_points(action: str | None, execution_bias: str | None, *, legacy_score: float = 0.0) -> float:
    action_points = {
        "accumulate": 1.6,
        "breakout_watch": 1.1,
        "wait_pullback": 0.2,
        "reduce_risk": -1.2,
        "avoid": -2.0,
    }.get(str(action or "").strip(), 0.0)
    bias_points = {
        "press_long": 2.0,
        "lean_long": 1.0,
        "stay_selective": 0.1,
        "reduce_risk": -1.4,
        "capital_preservation": -2.0,
    }.get(str(execution_bias or "").strip(), 0.0)
    legacy_points = _clip((float(legacy_score) - 70.0) * 0.03, -0.8, 1.2)
    return round(action_points + bias_points + legacy_points, 2)


@dataclass(slots=True)
class SelectionScoreResult:
    score: float
    normalized_score: float
    confidence_floor_passed: bool
    confidence_floor: float
    tiebreak_points: float
    components: dict[str, float]


def score_selection_candidate(
    *,
    expected_excess_return_pct: float,
    calibrated_confidence: float,
    probability_edge: float,
    tail_ratio: float,
    regime_alignment: float,
    analog_support: float | None,
    data_quality_support: float | None,
    downside_pct: float,
    forecast_volatility_pct: float,
    action: str | None = None,
    execution_bias: str | None = None,
    legacy_score: float = 0.0,
    confidence_floor: float = 62.0,
) -> SelectionScoreResult:
    positive_inputs: dict[str, tuple[float, float | None]] = {
        "expected_excess_return": (0.30, _clip(_sigmoid(float(expected_excess_return_pct) / 3.5), 0.0, 1.0)),
        "calibrated_confidence": (0.25, _clip(float(calibrated_confidence) / 100.0, 0.0, 1.0)),
        "probability_edge": (0.15, _clip(_sigmoid(float(probability_edge) / 10.0), 0.0, 1.0)),
        "tail_ratio": (0.10, _clip((float(tail_ratio) - 0.75) / 1.75, 0.0, 1.0)),
        "regime_alignment": (0.08, _clip(float(regime_alignment), 0.0, 1.0)),
        "analog_support": (0.07, _normalize_support(analog_support)),
        "data_quality": (0.05, _normalize_support(data_quality_support)),
    }
    active_positive_weight = sum(weight for weight, value in positive_inputs.values() if value is not None)
    positive_score = 0.0
    component_values: dict[str, float] = {}
    if active_positive_weight > 0:
        for key, (weight, value) in positive_inputs.items():
            if value is None:
                continue
            normalized_weight = weight / active_positive_weight
            positive_score += normalized_weight * float(value)
            component_values[key] = round(float(value), 4)

    downside_penalty = _clip(float(downside_pct) / 12.0, 0.0, 1.0)
    volatility_penalty = _clip(float(forecast_volatility_pct) / 28.0, 0.0, 1.0)
    raw_normalized = _clip(positive_score - 0.10 * downside_penalty - 0.05 * volatility_penalty, 0.0, 1.0)

    tiebreak_points = action_tiebreak_points(action, execution_bias, legacy_score=legacy_score)
    confidence_floor_passed = float(calibrated_confidence) >= float(confidence_floor)
    score = _clip(raw_normalized * 100.0 + tiebreak_points, 0.0, 100.0)
    if not confidence_floor_passed:
        score = min(score, confidence_floor - 0.5)

    component_values["downside_penalty"] = round(downside_penalty, 4)
    component_values["volatility_penalty"] = round(volatility_penalty, 4)

    return SelectionScoreResult(
        score=round(score, 1),
        normalized_score=round(raw_normalized, 4),
        confidence_floor_passed=confidence_floor_passed,
        confidence_floor=float(confidence_floor),
        tiebreak_points=tiebreak_points,
        components=component_values,
    )
