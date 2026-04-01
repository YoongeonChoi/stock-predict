from __future__ import annotations


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_float(value: float | None, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def scenario_snapshot(forecast) -> dict:
    scenarios = {item.name: item for item in getattr(forecast, "scenarios", [])}
    bull = scenarios.get("Bull")
    base = scenarios.get("Base")
    bear = scenarios.get("Bear")
    return {
        "bull_case_price": bull.price if bull else None,
        "base_case_price": base.price if base else None,
        "bear_case_price": bear.price if bear else None,
        "bull_probability": bull.probability if bull else None,
        "base_probability": base.probability if base else None,
        "bear_probability": bear.probability if bear else None,
    }

