from typing import Literal

from pydantic import BaseModel, Field


class ForecastScenario(BaseModel):
    name: str
    price: float
    probability: float
    description: str = ""


class IndexForecast(BaseModel):
    index_ticker: str
    index_name: str
    current_price: float
    fair_value: float
    scenarios: list[ForecastScenario]
    confidence_note: str = ""
    generated_at: str = ""


class FlowSignal(BaseModel):
    available: bool = False
    source: str = ""
    market: str = ""
    unit: str = ""
    foreign_net_buy: float | None = None
    institutional_net_buy: float | None = None
    retail_net_buy: float | None = None


class ForecastDriver(BaseModel):
    name: str
    value: float
    signal: Literal["bullish", "bearish", "neutral"]
    weight: float
    contribution: float
    detail: str = ""


class NextDayForecast(BaseModel):
    target_date: str
    reference_date: str
    reference_price: float
    direction: Literal["up", "down", "flat"]
    up_probability: float
    predicted_open: float | None = None
    predicted_close: float
    predicted_high: float
    predicted_low: float
    predicted_return_pct: float
    confidence: float
    raw_confidence: float | None = None
    calibrated_probability: float | None = None
    probability_edge: float | None = None
    analog_support: float | None = None
    regime_support: float | None = None
    agreement_support: float | None = None
    data_quality_support: float | None = None
    volatility_ratio: float | None = None
    confidence_calibrator: str | None = None
    calibration_snapshot: dict[str, object] | None = None
    fusion_method: str | None = None
    fusion_profile_sample_count: int | None = None
    fusion_blend_weight: float | None = None
    graph_context_used: bool | None = None
    graph_context_score: float | None = None
    graph_coverage: float | None = None
    fusion_profile_fitted_at: str | None = None
    confidence_note: str = ""
    news_sentiment: float = 0
    raw_signal: float = 0
    scenarios: list[ForecastScenario] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    execution_bias: Literal[
        "press_long",
        "lean_long",
        "stay_selective",
        "reduce_risk",
        "capital_preservation",
    ] = "stay_selective"
    execution_note: str = ""
    flow_signal: FlowSignal | None = None
    drivers: list[ForecastDriver] = Field(default_factory=list)
    model_version: str = "dist-studentt-v3.3-lfgraph"


class FreeKrForecastDataSource(BaseModel):
    name: str
    configured: bool
    used: bool
    item_count: int = 0
    note: str = ""


class FreeKrForecastEvidence(BaseModel):
    key: str
    label: str
    contribution: float
    signal: Literal["bullish", "bearish", "neutral"]
    detail: str = ""


class FreeKrForecastHorizon(BaseModel):
    horizon_days: int
    target_date: str
    mean_return_raw: float
    mean_return_excess: float
    q10: float
    q25: float
    q50: float
    q75: float
    q90: float
    price_q10: float
    price_q25: float
    price_q50: float
    price_q75: float
    price_q90: float
    p_down: float
    p_flat: float
    p_up: float
    vol_forecast: float
    confidence: float
    raw_confidence: float | None = None
    calibrated_probability: float | None = None
    probability_edge: float | None = None
    analog_support: float | None = None
    regime_support: float | None = None
    agreement_support: float | None = None
    data_quality_support: float | None = None
    volatility_ratio: float | None = None
    confidence_calibrator: str | None = None
    calibration_snapshot: dict[str, object] | None = None
    fusion_method: str | None = None
    fusion_profile_sample_count: int | None = None
    fusion_blend_weight: float | None = None
    graph_context_used: bool | None = None
    graph_context_score: float | None = None
    graph_coverage: float | None = None
    fusion_profile_fitted_at: str | None = None


class FreeKrForecast(BaseModel):
    reference_date: str
    reference_price: float
    regime: Literal["risk_on", "neutral", "risk_off"]
    regime_probs: dict[str, float]
    horizons: list[FreeKrForecastHorizon] = Field(default_factory=list)
    evidence: list[FreeKrForecastEvidence] = Field(default_factory=list)
    data_sources: list[FreeKrForecastDataSource] = Field(default_factory=list)
    confidence_note: str = ""
    summary: str = ""
    model_version: str = "dist-studentt-v3.3-lfgraph"


class HistoricalForecastHorizon(BaseModel):
    horizon_days: int
    sample_size: int
    up_probability: float
    expected_return_pct: float
    median_return_pct: float
    predicted_price: float
    range_low: float
    range_high: float
    realized_volatility_pct: float
    avg_max_drawdown_pct: float
    confidence: float
    analog_support: float | None = None
    effective_sample_size: float | None = None
    profit_factor: float | None = None


class HistoricalAnalogCase(BaseModel):
    date: str
    similarity: float
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None


class HistoricalPathPoint(BaseModel):
    offset: int
    target_date: str
    expected_price: float
    band_low: float
    band_high: float


class HistoricalPatternForecast(BaseModel):
    reference_date: str
    reference_price: float
    lookback_window_days: int
    analog_count: int
    feature_regime: str
    summary: str
    horizons: list[HistoricalForecastHorizon]
    analog_cases: list[HistoricalAnalogCase]
    projected_path: list[HistoricalPathPoint]
    model_version: str = "analog-v1.1"


class SetupBacktest(BaseModel):
    setup_label: str
    forward_horizon_days: int
    sample_size: int
    win_rate: float
    avg_return_pct: float
    median_return_pct: float
    avg_max_drawdown_pct: float
    best_return_pct: float
    worst_return_pct: float
    profit_factor: float | None = None
    confidence: float
    summary: str


class FearGreedComponent(BaseModel):
    name: str
    value: float
    signal: str
    weight: float = 0.2


class FearGreedIndex(BaseModel):
    score: float
    label: str
    components: list[FearGreedComponent]
    country_code: str

