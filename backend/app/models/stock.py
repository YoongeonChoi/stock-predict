from pydantic import BaseModel
from app.models.score import StockScore
from app.models.forecast import FreeKrForecast, HistoricalPatternForecast, NextDayForecast, SetupBacktest
from app.models.market import MarketRegime, TradePlan


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class TechnicalIndicators(BaseModel):
    ma_20: list[float | None]
    ma_60: list[float | None]
    rsi_14: list[float | None]
    macd: list[float | None]
    macd_signal: list[float | None]
    macd_hist: list[float | None]
    dates: list[str]


class QuarterlyFinancial(BaseModel):
    period: str
    revenue: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    ebitda: float | None = None
    free_cash_flow: float | None = None


class PeerComparison(BaseModel):
    metric: str
    company_value: float | None
    peer_avg: float | None
    sector_avg: float | None


class AnalystRatings(BaseModel):
    buy: int = 0
    hold: int = 0
    sell: int = 0
    target_mean: float | None = None
    target_median: float | None = None
    target_high: float | None = None
    target_low: float | None = None


class EarningsEvent(BaseModel):
    date: str
    eps_estimate: float | None = None
    eps_actual: float | None = None
    surprise_pct: float | None = None


class ValuationMethod(BaseModel):
    name: str
    value: float
    weight: float
    details: str = ""


class BuySellGuide(BaseModel):
    buy_zone_low: float
    buy_zone_high: float
    fair_value: float
    sell_zone_low: float
    sell_zone_high: float
    risk_reward_ratio: float
    confidence_grade: str
    methodology: list[ValuationMethod]
    summary: str = ""


class PublicStockSummary(BaseModel):
    summary: str
    evidence_for: list[str]
    evidence_against: list[str]
    why_not_buy_now: list[str]
    thesis_breakers: list[str]
    data_quality: str
    confidence_note: str


class DividendInfo(BaseModel):
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    dividend_growth_5y: float | None = None


class StockSummary(BaseModel):
    ticker: str
    name: str
    country_code: str
    sector: str
    current_price: float
    change_pct: float
    score_total: float | None = None


class StockDetail(BaseModel):
    ticker: str
    name: str
    country_code: str
    sector: str
    industry: str
    market_cap: float
    current_price: float
    change_pct: float

    financials: list[QuarterlyFinancial]
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None
    peg_ratio: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    peer_comparisons: list[PeerComparison]

    dividend: DividendInfo
    analyst_ratings: AnalystRatings
    earnings_history: list[EarningsEvent]

    price_history: list[PricePoint]
    technical: TechnicalIndicators

    score: StockScore
    buy_sell_guide: BuySellGuide
    next_day_forecast: NextDayForecast | None = None
    free_kr_forecast: FreeKrForecast | None = None
    historical_pattern_forecast: HistoricalPatternForecast | None = None
    setup_backtest: SetupBacktest | None = None
    market_regime: MarketRegime | None = None
    trade_plan: TradePlan | None = None
    public_summary: PublicStockSummary | None = None
    generated_at: str | None = None
    partial: bool | None = None
    fallback_reason: str | None = None
