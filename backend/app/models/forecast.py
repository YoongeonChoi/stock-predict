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
