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
    model_version: str = "signal-v2"


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
