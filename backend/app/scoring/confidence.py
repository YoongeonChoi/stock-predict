from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Iterable, Mapping, Sequence


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(value: float) -> float:
    if value >= 0:
        denominator = 1.0 + exp(-value)
        return 1.0 / denominator
    numerator = exp(value)
    return numerator / (1.0 + numerator)


def _normalize_support(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if numeric > 1.0:
        numeric /= 100.0
    return _clip(numeric, 0.0, 1.0)


def effective_sample_size(weights: Sequence[float] | Iterable[float]) -> float:
    values = [max(float(weight), 0.0) for weight in weights]
    total = sum(values)
    if total <= 0:
        return 0.0
    normalized = [value / total for value in values]
    squared_sum = sum(value * value for value in normalized)
    if squared_sum <= 0:
        return 0.0
    return 1.0 / squared_sum


def analog_support_score(
    *,
    win_rate_pct: float,
    ess: float,
    profit_factor: float | None,
    dispersion_pct: float,
    reference_volatility_pct: float,
) -> float:
    win_component = _clip(float(win_rate_pct) / 100.0, 0.0, 1.0)
    ess_component = _clip(log(1.0 + max(float(ess), 0.0)) / log(21.0), 0.0, 1.0)
    profit_component = _clip((float(profit_factor) if profit_factor is not None else 0.0) / 2.5, 0.0, 1.0)
    volatility_reference = max(float(reference_volatility_pct), 0.5)
    dispersion_component = 1.0 - _clip(float(dispersion_pct) / volatility_reference, 0.0, 1.0)
    return _clip(
        0.45 * win_component
        + 0.25 * ess_component
        + 0.15 * profit_component
        + 0.15 * dispersion_component,
        0.0,
        1.0,
    )


def build_regime_support(regime_probs: Mapping[str, float] | None) -> float:
    if not regime_probs:
        return 0.0
    dominant = max((float(value) for value in regime_probs.values()), default=33.3)
    return _clip((dominant - 33.3) / 66.7, 0.0, 1.0)


def build_data_quality_support(
    *,
    history_bars: int,
    macro_available: bool,
    fundamental_available: bool,
    flow_available: bool,
    event_count: int,
    event_uncertainty: float,
) -> float:
    history_component = _clip(float(history_bars) / 252.0, 0.0, 1.0)
    event_component = _clip(float(event_count) / 5.0, 0.0, 1.0) * max(0.25, 1.0 - _clip(event_uncertainty, 0.0, 1.0))
    return _clip(
        0.50 * history_component
        + 0.15 * (1.0 if macro_available else 0.0)
        + 0.15 * (1.0 if fundamental_available else 0.0)
        + 0.10 * (1.0 if flow_available else 0.0)
        + 0.10 * event_component,
        0.0,
        1.0,
    )


def build_agreement_support(signals: Sequence[float | None]) -> float | None:
    normalized: list[int] = []
    for signal in signals:
        if signal is None:
            continue
        value = float(signal)
        if value > 1e-8:
            normalized.append(1)
        elif value < -1e-8:
            normalized.append(-1)
        else:
            normalized.append(0)
    if len(normalized) < 2:
        return None

    total_pairs = 0
    matches = 0.0
    for left_index in range(len(normalized)):
        for right_index in range(left_index + 1, len(normalized)):
            left = normalized[left_index]
            right = normalized[right_index]
            total_pairs += 1
            if left == right:
                matches += 1.0
            elif left == 0 or right == 0:
                matches += 0.5
    if total_pairs <= 0:
        return None
    return _clip(matches / total_pairs, 0.0, 1.0)


@dataclass(slots=True)
class ConfidenceResult:
    display_confidence: float
    calibrated_probability: float
    raw_confidence: float
    distribution_support: float
    analog_support: float | None
    regime_support: float
    edge_support: float
    agreement_support: float | None
    data_quality_support: float
    uncertainty_support: float
    volatility_support: float
    volatility_ratio: float
    calibrator_method: str


CALIBRATION_PARAMS: dict[int, dict[str, float]] = {
    1: {"slope": 8.0, "center": 0.54},
    5: {"slope": 7.2, "center": 0.57},
    20: {"slope": 6.4, "center": 0.60},
}
BOOTSTRAP_CONFIDENCE_MAX = 0.88


def calibrate_direction_confidence(
    *,
    horizon_days: int,
    distribution_confidence: float,
    p_up: float,
    p_down: float,
    regime_probs: Mapping[str, float] | None,
    median_return_pct: float,
    history_bars: int,
    macro_available: bool,
    fundamental_available: bool,
    flow_available: bool,
    event_count: int,
    event_uncertainty: float,
    forecast_volatility_pct: float,
    realized_volatility_reference_pct: float,
    analog_support: float | None = None,
    analog_expected_return_pct: float | None = None,
) -> ConfidenceResult:
    distribution_support = _clip(float(distribution_confidence) / 100.0, 0.0, 1.0)
    edge_support = _clip(abs(float(p_up) - float(p_down)) / 100.0, 0.0, 1.0)
    regime_support = build_regime_support(regime_probs)

    dominant_regime_signal = None
    if regime_probs:
        dominant_regime = max(regime_probs, key=regime_probs.get)
        dominant_regime_signal = 1.0 if dominant_regime == "risk_on" else -1.0 if dominant_regime == "risk_off" else 0.0

    agreement_support = build_agreement_support(
        [float(median_return_pct), analog_expected_return_pct, dominant_regime_signal]
    )
    data_quality_support = build_data_quality_support(
        history_bars=history_bars,
        macro_available=macro_available,
        fundamental_available=fundamental_available,
        flow_available=flow_available,
        event_count=event_count,
        event_uncertainty=event_uncertainty,
    )
    uncertainty_support = 1.0 - _clip(float(event_uncertainty), 0.0, 1.0)
    reference_volatility = max(float(realized_volatility_reference_pct), 0.01)
    volatility_ratio = _clip(float(forecast_volatility_pct) / reference_volatility, 0.0, 2.0)
    volatility_support = 1.0 - _clip(volatility_ratio, 0.0, 1.0)
    normalized_analog_support = _normalize_support(analog_support)

    support_map: dict[str, tuple[float, float | None]] = {
        "distribution": (0.35, distribution_support),
        "analog": (0.18, normalized_analog_support),
        "regime": (0.08, regime_support),
        "edge": (0.12, edge_support),
        "agreement": (0.10, agreement_support),
        "quality": (0.07, data_quality_support),
        "uncertainty": (0.05, uncertainty_support),
        "volatility": (0.05, volatility_support),
    }
    available_weight = sum(weight for weight, value in support_map.values() if value is not None)
    raw_support = 0.0
    if available_weight > 0:
        for weight, value in support_map.values():
            if value is None:
                continue
            raw_support += (weight / available_weight) * float(value)
    raw_confidence = _clip(raw_support * 100.0, 0.0, 100.0)

    bucket = 1 if horizon_days <= 1 else 5 if horizon_days <= 5 else 20
    params = CALIBRATION_PARAMS[bucket]
    calibrated_probability = _clip(
        _sigmoid(params["slope"] * (raw_support - params["center"])),
        0.0,
        BOOTSTRAP_CONFIDENCE_MAX,
    )
    display_confidence = calibrated_probability * 100.0
    calibrator_method = f"bootstrap_sigmoid_{bucket}d"

    return ConfidenceResult(
        display_confidence=round(display_confidence, 1),
        calibrated_probability=round(calibrated_probability, 4),
        raw_confidence=round(raw_confidence, 1),
        distribution_support=round(distribution_support, 4),
        analog_support=round(float(normalized_analog_support), 4) if normalized_analog_support is not None else None,
        regime_support=round(regime_support, 4),
        edge_support=round(edge_support, 4),
        agreement_support=round(float(agreement_support), 4) if agreement_support is not None else None,
        data_quality_support=round(data_quality_support, 4),
        uncertainty_support=round(uncertainty_support, 4),
        volatility_support=round(volatility_support, 4),
        volatility_ratio=round(volatility_ratio, 4),
        calibrator_method=calibrator_method,
    )
