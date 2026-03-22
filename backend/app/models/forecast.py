from typing import Literal

from pydantic import BaseModel


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
    confidence_note: str = ""
    news_sentiment: float = 0
    raw_signal: float = 0
    flow_signal: FlowSignal | None = None
    drivers: list[ForecastDriver] = []
    model_version: str = "signal-v2.3"


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
    model_version: str = "analog-v1.0"


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

