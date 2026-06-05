from __future__ import annotations

import copy
from typing import Any

POLICY_VERSION = "investment-policy-v1"

PROFILE_STYLE_LABELS = {
    "defensive": "방어형",
    "balanced": "균형형",
    "offensive": "공격형",
}

PROFILE_PRESETS: dict[str, dict[str, float | int | str]] = {
    "capital_preservation": {
        "label": "원금보존형",
        "optimization_style": "defensive",
        "recommended_equity_pct": 58.0,
        "cash_buffer_pct": 42.0,
        "target_position_count": 5,
        "max_single_weight_pct": 9.5,
        "max_country_weight_pct": 36.0,
        "max_sector_weight_pct": 20.0,
        "min_confidence": 68.0,
        "min_up_probability": 56.0,
        "max_down_probability": 24.0,
        "risk_aversion": 11.0,
        "turnover_penalty": 0.012,
        "expected_excess_weight": 0.75,
        "expected_total_weight": 0.20,
        "probability_edge_weight": 0.025,
    },
    "conservative": {
        "label": "안정추구형",
        "optimization_style": "defensive",
        "recommended_equity_pct": 70.0,
        "cash_buffer_pct": 30.0,
        "target_position_count": 6,
        "max_single_weight_pct": 11.5,
        "max_country_weight_pct": 42.0,
        "max_sector_weight_pct": 24.0,
        "min_confidence": 65.0,
        "min_up_probability": 55.0,
        "max_down_probability": 28.0,
        "risk_aversion": 8.8,
        "turnover_penalty": 0.009,
        "expected_excess_weight": 0.90,
        "expected_total_weight": 0.28,
        "probability_edge_weight": 0.035,
    },
    "balanced": {
        "label": "균형형",
        "optimization_style": "balanced",
        "recommended_equity_pct": 82.0,
        "cash_buffer_pct": 18.0,
        "target_position_count": 7,
        "max_single_weight_pct": 14.5,
        "max_country_weight_pct": 48.0,
        "max_sector_weight_pct": 28.0,
        "min_confidence": 62.0,
        "min_up_probability": 54.0,
        "max_down_probability": 34.0,
        "risk_aversion": 6.0,
        "turnover_penalty": 0.006,
        "expected_excess_weight": 1.00,
        "expected_total_weight": 0.35,
        "probability_edge_weight": 0.045,
    },
    "growth": {
        "label": "성장추구형",
        "optimization_style": "offensive",
        "recommended_equity_pct": 90.0,
        "cash_buffer_pct": 10.0,
        "target_position_count": 7,
        "max_single_weight_pct": 17.5,
        "max_country_weight_pct": 56.0,
        "max_sector_weight_pct": 36.0,
        "min_confidence": 59.0,
        "min_up_probability": 53.0,
        "max_down_probability": 39.0,
        "risk_aversion": 4.8,
        "turnover_penalty": 0.0045,
        "expected_excess_weight": 1.15,
        "expected_total_weight": 0.45,
        "probability_edge_weight": 0.055,
    },
    "aggressive": {
        "label": "적극투자형",
        "optimization_style": "offensive",
        "recommended_equity_pct": 94.0,
        "cash_buffer_pct": 6.0,
        "target_position_count": 8,
        "max_single_weight_pct": 21.0,
        "max_country_weight_pct": 64.0,
        "max_sector_weight_pct": 42.0,
        "min_confidence": 56.0,
        "min_up_probability": 52.0,
        "max_down_probability": 45.0,
        "risk_aversion": 3.8,
        "turnover_penalty": 0.003,
        "expected_excess_weight": 1.30,
        "expected_total_weight": 0.55,
        "probability_edge_weight": 0.065,
    },
}

PROFILE_CODES = tuple(PROFILE_PRESETS.keys())


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_known_profile_code(value: str | None) -> bool:
    return str(value or "").strip().lower() in PROFILE_PRESETS


def normalize_profile_code(value: str | None) -> str:
    normalized = str(value or "balanced").strip().lower() or "balanced"
    return normalized if normalized in PROFILE_PRESETS else "balanced"


def profile_code_to_optimization_style(profile_code: str) -> str:
    preset = PROFILE_PRESETS[normalize_profile_code(profile_code)]
    return str(preset["optimization_style"])


def _market_stance_counts(market_view: list[dict] | None) -> dict[str, int]:
    counts = {"risk_on": 0, "risk_off": 0, "neutral": 0}
    for item in market_view or []:
        stance = str(item.get("stance") or (item.get("market_regime") or {}).get("stance") or "neutral")
        if stance in counts:
            counts[stance] += 1
        else:
            counts["neutral"] += 1
    return counts


def _apply_overrides(policy: dict, overrides: dict | None) -> None:
    if not overrides:
        return

    allowed_numeric = {
        "recommended_equity_pct",
        "cash_buffer_pct",
        "target_position_count",
        "max_single_weight_pct",
        "max_country_weight_pct",
        "max_sector_weight_pct",
        "min_confidence",
        "min_up_probability",
        "max_down_probability",
        "risk_aversion",
        "turnover_penalty",
        "expected_excess_weight",
        "expected_total_weight",
        "probability_edge_weight",
    }
    for key in allowed_numeric:
        if key in overrides and overrides[key] is not None:
            policy[key] = _as_float(overrides[key], _as_float(policy.get(key)))

    style = str(overrides.get("style") or "").strip().lower()
    if style in PROFILE_STYLE_LABELS:
        policy["style"] = style
        policy["style_label"] = PROFILE_STYLE_LABELS[style]


def _clamp_policy(policy: dict) -> dict:
    cash = _clip(_as_float(policy.get("cash_buffer_pct"), 18.0), 3.0, 60.0)
    equity = _clip(100.0 - cash, 40.0, 97.0)
    cash = _clip(100.0 - equity, 3.0, 60.0)

    policy["cash_buffer_pct"] = round(cash, 2)
    policy["recommended_equity_pct"] = round(100.0 - cash, 2)
    policy["target_position_count"] = int(_clip(_as_float(policy.get("target_position_count"), 7.0), 3.0, 10.0))
    policy["max_single_weight_pct"] = round(_clip(_as_float(policy.get("max_single_weight_pct"), 14.5), 6.0, 24.0), 2)
    policy["max_country_weight_pct"] = round(_clip(_as_float(policy.get("max_country_weight_pct"), 48.0), 30.0, 70.0), 2)
    policy["max_sector_weight_pct"] = round(_clip(_as_float(policy.get("max_sector_weight_pct"), 28.0), 18.0, 45.0), 2)
    policy["min_confidence"] = round(_clip(_as_float(policy.get("min_confidence"), 62.0), 50.0, 75.0), 2)
    policy["min_up_probability"] = round(_clip(_as_float(policy.get("min_up_probability"), 54.0), 50.0, 65.0), 2)
    policy["max_down_probability"] = round(_clip(_as_float(policy.get("max_down_probability"), 34.0), 20.0, 48.0), 2)
    return policy


def build_recommendation_policy(
    profile: dict | None,
    *,
    portfolio_risk: dict | None = None,
    market_view: list[dict] | None = None,
    overrides: dict | None = None,
) -> dict:
    profile_code = normalize_profile_code((profile or {}).get("profile_code"))
    preset = copy.deepcopy(PROFILE_PRESETS[profile_code])
    style = str(preset["optimization_style"])
    policy = {
        "profile_code": profile_code,
        "profile_label": str(preset["label"]),
        "profile_persisted": bool((profile or {}).get("persisted")),
        "profile_fallback_reason": (profile or {}).get("fallback_reason"),
        "policy_version": POLICY_VERSION,
        "style": style,
        "style_label": PROFILE_STYLE_LABELS[style],
        "recommended_equity_pct": float(preset["recommended_equity_pct"]),
        "cash_buffer_pct": float(preset["cash_buffer_pct"]),
        "target_position_count": int(preset["target_position_count"]),
        "max_single_weight_pct": float(preset["max_single_weight_pct"]),
        "max_country_weight_pct": float(preset["max_country_weight_pct"]),
        "max_sector_weight_pct": float(preset["max_sector_weight_pct"]),
        "min_confidence": float(preset["min_confidence"]),
        "min_up_probability": float(preset["min_up_probability"]),
        "max_down_probability": float(preset["max_down_probability"]),
        "risk_aversion": float(preset["risk_aversion"]),
        "turnover_penalty": float(preset["turnover_penalty"]),
        "expected_excess_weight": float(preset["expected_excess_weight"]),
        "expected_total_weight": float(preset["expected_total_weight"]),
        "probability_edge_weight": float(preset["probability_edge_weight"]),
        "dynamic_adjustments": [],
    }
    _apply_overrides(policy, overrides)

    risk = portfolio_risk or {}
    stance_counts = _market_stance_counts(market_view)
    risk_off_weight = _as_float(risk.get("risk_off_weight"), 0.0)
    risk_off_regime_weight = sum(
        _as_float(item.get("weight"), 0.0)
        for item in risk.get("regimes", []) or []
        if item.get("stance") == "risk_off"
    )
    if stance_counts["risk_off"] > 0 or risk_off_weight >= 35.0 or risk_off_regime_weight >= 35.0:
        policy["cash_buffer_pct"] = _as_float(policy["cash_buffer_pct"]) + 5.0
        policy["max_single_weight_pct"] = _as_float(policy["max_single_weight_pct"]) - 1.2
        policy["dynamic_adjustments"].append("시장 또는 보유 시장 비중에 risk-off 신호가 있어 현금 버퍼와 단일 종목 상한을 보수적으로 조정했습니다.")

    overall_label = str(risk.get("overall_label") or "")
    if overall_label in {"aggressive", "elevated"}:
        policy["cash_buffer_pct"] = _as_float(policy["cash_buffer_pct"]) + (7.0 if overall_label == "aggressive" else 4.0)
        policy["max_single_weight_pct"] = _as_float(policy["max_single_weight_pct"]) - (2.0 if overall_label == "aggressive" else 1.2)
        policy["dynamic_adjustments"].append("현재 포트폴리오 위험도가 높아 성향과 무관하게 현금 버퍼를 늘리고 단일 종목 상한을 낮췄습니다.")

    portfolio_up_probability = _as_float(risk.get("portfolio_up_probability"), 50.0)
    if portfolio_up_probability <= 47.0:
        policy["cash_buffer_pct"] = _as_float(policy["cash_buffer_pct"]) + 4.0
        policy["dynamic_adjustments"].append("포트폴리오 상승 확률이 낮아 신규 주식 비중을 줄였습니다.")
    elif portfolio_up_probability <= 50.0:
        policy["cash_buffer_pct"] = _as_float(policy["cash_buffer_pct"]) + 2.0
        policy["dynamic_adjustments"].append("포트폴리오 상승 확률이 중립 이하라 현금 버퍼를 조금 높였습니다.")
    elif (
        portfolio_up_probability >= 58.0
        and stance_counts["risk_on"] > 0
        and stance_counts["risk_off"] == 0
        and profile_code in {"growth", "aggressive"}
    ):
        policy["cash_buffer_pct"] = _as_float(policy["cash_buffer_pct"]) - 2.0
        policy["dynamic_adjustments"].append("상승 확률과 risk-on 환경이 동시에 확인되어 성장형 성향의 주식 비중을 소폭 높였습니다.")

    return _clamp_policy(policy)


def recommendation_policy_public_view(policy: dict | None) -> dict | None:
    if not policy:
        return None
    resolved_keys = [
        "recommended_equity_pct",
        "cash_buffer_pct",
        "target_position_count",
        "max_single_weight_pct",
        "max_country_weight_pct",
        "max_sector_weight_pct",
        "min_confidence",
        "min_up_probability",
        "max_down_probability",
        "risk_aversion",
        "turnover_penalty",
        "expected_excess_weight",
        "expected_total_weight",
        "probability_edge_weight",
    ]
    return {
        "profile_code": policy.get("profile_code"),
        "profile_label": policy.get("profile_label"),
        "profile_persisted": bool(policy.get("profile_persisted")),
        "profile_fallback_reason": policy.get("profile_fallback_reason"),
        "policy_version": policy.get("policy_version", POLICY_VERSION),
        "style": policy.get("style"),
        "style_label": policy.get("style_label"),
        "resolved_params": {key: policy.get(key) for key in resolved_keys},
        "dynamic_adjustments": list(policy.get("dynamic_adjustments") or []),
    }
