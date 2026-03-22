from typing import Literal

from pydantic import BaseModel


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
    playbook: list[str] = []
    warnings: list[str] = []
    signals: list[MarketRegimeSignal] = []


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
    thesis: list[str] = []
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
    setup_label: str
    action: str
    regime_tailwind: str
    entry_low: float | None = None
    entry_high: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    risk_reward_estimate: float = 0
    thesis: list[str] = []
    forecast_date: str = ""


class OpportunityRadarResponse(BaseModel):
    country_code: str
    generated_at: str
    market_regime: MarketRegime
    total_scanned: int
    actionable_count: int
    bullish_count: int
    opportunities: list[OpportunityItem]
