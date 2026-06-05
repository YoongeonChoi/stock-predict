from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.data.supabase_client import supabase_client
from app.errors import SP_6020
from app.exceptions import ApiAppException
from app.models.investment_profile import (
    InvestmentProfile,
    InvestmentProfileOption,
    InvestmentProfileOptionsResponse,
    InvestmentProfileResolveRequest,
    InvestmentProfileResolveResponse,
    InvestmentProfileUpdateRequest,
)
from app.services.recommendation_policy import POLICY_VERSION, PROFILE_PRESETS, is_known_profile_code, normalize_profile_code

PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "capital_preservation": {
        "risk_tolerance": 1,
        "investment_horizon": "short",
        "max_drawdown_pct": 6.0,
        "turnover_preference": "low",
        "concentration_preference": "low",
        "cash_buffer_min_pct": 30.0,
        "cash_buffer_max_pct": 60.0,
    },
    "conservative": {
        "risk_tolerance": 2,
        "investment_horizon": "medium",
        "max_drawdown_pct": 10.0,
        "turnover_preference": "low",
        "concentration_preference": "low",
        "cash_buffer_min_pct": 20.0,
        "cash_buffer_max_pct": 40.0,
    },
    "balanced": {
        "risk_tolerance": 3,
        "investment_horizon": "medium",
        "max_drawdown_pct": 15.0,
        "turnover_preference": "medium",
        "concentration_preference": "medium",
        "cash_buffer_min_pct": 10.0,
        "cash_buffer_max_pct": 25.0,
    },
    "growth": {
        "risk_tolerance": 4,
        "investment_horizon": "long",
        "max_drawdown_pct": 22.0,
        "turnover_preference": "medium",
        "concentration_preference": "medium",
        "cash_buffer_min_pct": 6.0,
        "cash_buffer_max_pct": 18.0,
    },
    "aggressive": {
        "risk_tolerance": 5,
        "investment_horizon": "swing",
        "max_drawdown_pct": 30.0,
        "turnover_preference": "high",
        "concentration_preference": "high",
        "cash_buffer_min_pct": 3.0,
        "cash_buffer_max_pct": 12.0,
    },
}

PROFILE_DESCRIPTIONS = {
    "capital_preservation": "현금 비중과 하락 방어를 우선합니다.",
    "conservative": "확신도와 분산을 중시합니다.",
    "balanced": "수익과 리스크를 균형 있게 반영합니다.",
    "growth": "기대초과수익과 상승 확률을 더 중시합니다.",
    "aggressive": "높은 기회 점수를 더 적극 반영하되 손실 guard는 유지합니다.",
}

HORIZONS = {"short", "swing", "medium", "long"}
PREFERENCES = {"low", "medium", "high"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_label(profile_code: str) -> str:
    return str(PROFILE_PRESETS[normalize_profile_code(profile_code)]["label"])


def _value(data: dict[str, Any], key: str, default: Any) -> Any:
    value = data.get(key)
    return default if value is None else value


def _build_profile(data: dict[str, Any], *, persisted: bool) -> InvestmentProfile:
    profile_code = normalize_profile_code(data.get("profile_code"))
    defaults = PROFILE_DEFAULTS[profile_code]
    return InvestmentProfile(
        profile_code=profile_code,  # type: ignore[arg-type]
        profile_label=_profile_label(profile_code),
        risk_tolerance=int(_value(data, "risk_tolerance", defaults["risk_tolerance"])),
        investment_horizon=str(_value(data, "investment_horizon", defaults["investment_horizon"])),  # type: ignore[arg-type]
        max_drawdown_pct=float(_value(data, "max_drawdown_pct", defaults["max_drawdown_pct"])),
        turnover_preference=str(_value(data, "turnover_preference", defaults["turnover_preference"])),  # type: ignore[arg-type]
        concentration_preference=str(_value(data, "concentration_preference", defaults["concentration_preference"])),  # type: ignore[arg-type]
        cash_buffer_min_pct=float(_value(data, "cash_buffer_min_pct", defaults["cash_buffer_min_pct"])),
        cash_buffer_max_pct=float(_value(data, "cash_buffer_max_pct", defaults["cash_buffer_max_pct"])),
        policy_version=str(data.get("policy_version") or POLICY_VERSION),
        questionnaire_json=data.get("questionnaire_json") if isinstance(data.get("questionnaire_json"), dict) else {},
        updated_at=data.get("updated_at"),
        persisted=persisted,
    )


def get_default_investment_profile() -> InvestmentProfile:
    return _build_profile({"profile_code": "balanced", "policy_version": POLICY_VERSION}, persisted=False)


def _validate_payload(payload: InvestmentProfileUpdateRequest) -> dict[str, Any]:
    profile_code = payload.profile_code or "balanced"
    if not is_known_profile_code(profile_code):
        raise ApiAppException(400, SP_6020("투자 성향 코드를 확인해 주세요."))

    normalized_code = normalize_profile_code(profile_code)
    defaults = PROFILE_DEFAULTS[normalized_code]
    risk_tolerance = int(payload.risk_tolerance if payload.risk_tolerance is not None else defaults["risk_tolerance"])
    if risk_tolerance < 1 or risk_tolerance > 5:
        raise ApiAppException(400, SP_6020("위험 선호도는 1~5 사이로 입력해 주세요."))

    investment_horizon = str(payload.investment_horizon or defaults["investment_horizon"])
    if investment_horizon not in HORIZONS:
        raise ApiAppException(400, SP_6020("투자 기간은 short, swing, medium, long 중 하나여야 합니다."))

    turnover_preference = str(payload.turnover_preference or defaults["turnover_preference"])
    if turnover_preference not in PREFERENCES:
        raise ApiAppException(400, SP_6020("회전율 선호는 low, medium, high 중 하나여야 합니다."))

    concentration_preference = str(payload.concentration_preference or defaults["concentration_preference"])
    if concentration_preference not in PREFERENCES:
        raise ApiAppException(400, SP_6020("집중도 선호는 low, medium, high 중 하나여야 합니다."))

    max_drawdown_pct = float(payload.max_drawdown_pct if payload.max_drawdown_pct is not None else defaults["max_drawdown_pct"])
    if max_drawdown_pct <= 0 or max_drawdown_pct > 80:
        raise ApiAppException(400, SP_6020("허용 손실률은 0보다 크고 80% 이하여야 합니다."))

    cash_buffer_min_pct = float(payload.cash_buffer_min_pct if payload.cash_buffer_min_pct is not None else defaults["cash_buffer_min_pct"])
    cash_buffer_max_pct = float(payload.cash_buffer_max_pct if payload.cash_buffer_max_pct is not None else defaults["cash_buffer_max_pct"])
    if cash_buffer_min_pct < 0 or cash_buffer_max_pct > 80 or cash_buffer_min_pct > cash_buffer_max_pct:
        raise ApiAppException(400, SP_6020("현금 버퍼 범위는 0~80% 안에서 최소값이 최대값보다 작아야 합니다."))

    questionnaire_json = payload.questionnaire_json if isinstance(payload.questionnaire_json, dict) else {}

    return {
        "profile_code": normalized_code,
        "risk_tolerance": risk_tolerance,
        "investment_horizon": investment_horizon,
        "max_drawdown_pct": max_drawdown_pct,
        "turnover_preference": turnover_preference,
        "concentration_preference": concentration_preference,
        "cash_buffer_min_pct": cash_buffer_min_pct,
        "cash_buffer_max_pct": cash_buffer_max_pct,
        "policy_version": POLICY_VERSION,
        "questionnaire_json": questionnaire_json,
        "updated_at": _utcnow_iso(),
    }


async def get_investment_profile(user_id: str) -> InvestmentProfile:
    row = await supabase_client.investment_profile_get(user_id)
    if not row:
        return get_default_investment_profile()
    return _build_profile(row, persisted=True)


async def update_investment_profile(user_id: str, payload: InvestmentProfileUpdateRequest) -> InvestmentProfile:
    normalized = _validate_payload(payload)
    saved = await supabase_client.investment_profile_upsert(user_id, normalized)
    return _build_profile(saved or normalized, persisted=True)


def get_investment_profile_options() -> InvestmentProfileOptionsResponse:
    options: list[InvestmentProfileOption] = []
    for profile_code, preset in PROFILE_PRESETS.items():
        defaults = PROFILE_DEFAULTS[profile_code]
        options.append(
            InvestmentProfileOption(
                profile_code=profile_code,  # type: ignore[arg-type]
                profile_label=str(preset["label"]),
                description=PROFILE_DESCRIPTIONS[profile_code],
                risk_tolerance=int(defaults["risk_tolerance"]),
                recommended_equity_pct=float(preset["recommended_equity_pct"]),
                cash_buffer_pct=float(preset["cash_buffer_pct"]),
                max_single_weight_pct=float(preset["max_single_weight_pct"]),
                optimization_style=str(preset["optimization_style"]),
            )
        )
    return InvestmentProfileOptionsResponse(policy_version=POLICY_VERSION, options=options)


def resolve_profile_from_questionnaire(payload: InvestmentProfileResolveRequest) -> InvestmentProfileResolveResponse:
    mapping = {
        1: "capital_preservation",
        2: "conservative",
        3: "balanced",
        4: "growth",
        5: "aggressive",
    }
    profile_code = mapping[int(payload.risk_tolerance)]
    profile = _build_profile(
        {
            "profile_code": profile_code,
            "risk_tolerance": payload.risk_tolerance,
            "investment_horizon": payload.investment_horizon,
            "max_drawdown_pct": payload.max_drawdown_pct,
            "turnover_preference": payload.turnover_preference,
            "concentration_preference": payload.concentration_preference,
            "policy_version": POLICY_VERSION,
        },
        persisted=False,
    )
    return InvestmentProfileResolveResponse(
        profile_code=profile.profile_code,
        profile_label=profile.profile_label,
        reason=f"위험 선호도 {payload.risk_tolerance}단계를 기준으로 {profile.profile_label}을 제안합니다.",
        profile=profile,
    )
