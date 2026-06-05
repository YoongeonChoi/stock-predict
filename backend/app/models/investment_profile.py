from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

InvestmentProfileCode = Literal[
    "capital_preservation",
    "conservative",
    "balanced",
    "growth",
    "aggressive",
]
InvestmentHorizon = Literal["short", "swing", "medium", "long"]
TurnoverPreference = Literal["low", "medium", "high"]
ConcentrationPreference = Literal["low", "medium", "high"]


class InvestmentProfile(BaseModel):
    profile_code: InvestmentProfileCode
    profile_label: str
    risk_tolerance: int = Field(ge=1, le=5)
    investment_horizon: InvestmentHorizon
    max_drawdown_pct: float
    turnover_preference: TurnoverPreference
    concentration_preference: ConcentrationPreference
    cash_buffer_min_pct: float
    cash_buffer_max_pct: float
    policy_version: str
    questionnaire_json: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None
    persisted: bool = False


class InvestmentProfileUpdateRequest(BaseModel):
    profile_code: str | None = None
    risk_tolerance: int | None = None
    investment_horizon: str | None = None
    max_drawdown_pct: float | None = None
    turnover_preference: str | None = None
    concentration_preference: str | None = None
    cash_buffer_min_pct: float | None = None
    cash_buffer_max_pct: float | None = None
    questionnaire_json: dict[str, Any] | None = None


class InvestmentProfileOption(BaseModel):
    profile_code: InvestmentProfileCode
    profile_label: str
    description: str
    risk_tolerance: int
    recommended_equity_pct: float
    cash_buffer_pct: float
    max_single_weight_pct: float
    optimization_style: str


class InvestmentProfileOptionsResponse(BaseModel):
    policy_version: str
    options: list[InvestmentProfileOption]


class InvestmentProfileResolveRequest(BaseModel):
    risk_tolerance: int = Field(ge=1, le=5)
    investment_horizon: str | None = None
    max_drawdown_pct: float | None = None
    turnover_preference: str | None = None
    concentration_preference: str | None = None


class InvestmentProfileResolveResponse(BaseModel):
    profile_code: InvestmentProfileCode
    profile_label: str
    reason: str
    profile: InvestmentProfile
