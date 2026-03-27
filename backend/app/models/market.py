from typing import Literal

from pydantic import BaseModel, Field


class MarketRegimeSignal(BaseModel):
    name: str
    value: float
    signal: Literal["bullish", "bearish", "neutral"]
    detail: str = ""


class MarketRegime(BaseModel):
    label: str
    stance: Literal["risk_on", "neutral", "risk_off"]
    trend: Literal["uptrend", "range", "downtrend"]
    volatility: Literal["low", "normal", "high"]
    breadth: Literal["strong", "mixed", "weak"]
    score: float
    conviction: float
    summary: str
    playbook: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    signals: list[MarketRegimeSignal] = Field(default_factory=list)


class TradePlan(BaseModel):
    setup_label: str
    action: Literal["accumulate", "breakout_watch", "wait_pullback", "reduce_risk", "avoid"]
    conviction: float
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    expected_holding_days: int = 5
    risk_reward_estimate: float = 0
    thesis: list[str] = Field(default_factory=list)
    invalidation: str = ""


class OpportunityItem(BaseModel):
    rank: int
    ticker: str
    name: str
    sector: str
    country_code: str
    current_price: float
    change_pct: float
    opportunity_score: float
    quant_score: float
    up_probability: float
    confidence: float
    predicted_return_pct: float
    target_horizon_days: int = 20
    target_date_20d: str | None = None
    expected_return_pct_20d: float | None = None
    expected_excess_return_pct_20d: float | None = None
    median_return_pct_20d: float | None = None
    forecast_volatility_pct_20d: float | None = None
    up_probability_20d: float | None = None
    flat_probability_20d: float | None = None
    down_probability_20d: float | None = None
    distribution_confidence_20d: float | None = None
    price_q25_20d: float | None = None
    price_q50_20d: float | None = None
    price_q75_20d: float | None = None
    bull_case_price: float | None = None
    base_case_price: float | None = None
    bear_case_price: float | None = None
    bull_probability: float | None = None
    base_probability: float | None = None
    bear_probability: float | None = None
    setup_label: str
    action: str
    execution_bias: str = "stay_selective"
    execution_note: str = ""
    regime_tailwind: str
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    risk_reward_estimate: float = 0
    thesis: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    forecast_date: str = ""


class OpportunityRadarResponse(BaseModel):
    country_code: str
    generated_at: str
    market_regime: MarketRegime
    universe_size: int
    total_scanned: int
    quote_available_count: int = 0
    detailed_scanned_count: int
    actionable_count: int
    bullish_count: int
    universe_source: Literal["dynamic", "fallback", "krx_listing"] = "fallback"
    universe_note: str = ""
    opportunities: list[OpportunityItem]
