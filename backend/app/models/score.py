from pydantic import BaseModel


class ScoreItem(BaseModel):
    name: str
    score: float
    max_score: float
    description: str = ""


class CountryScore(BaseModel):
    total: float
    monetary_policy: ScoreItem
    economic_growth: ScoreItem
    market_valuation: ScoreItem
    earnings_momentum: ScoreItem
    institutional_consensus: ScoreItem
    risk_assessment: ScoreItem


class StockScoreDetail(BaseModel):
    total: float
    max_score: float
    items: list[ScoreItem]


class StockScore(BaseModel):
    total: float
    fundamental: StockScoreDetail
    valuation: StockScoreDetail
    growth_momentum: StockScoreDetail
    analyst: StockScoreDetail
    risk: StockScoreDetail


class CompositeScore(BaseModel):
    """Composite score merging fundamentals, valuation, growth, analyst, risk, and technical analysis."""
    total: float
    total_raw: float
    max_raw: float
    fundamental: StockScoreDetail
    valuation: StockScoreDetail
    growth_momentum: StockScoreDetail
    analyst: StockScoreDetail
    risk: StockScoreDetail
    technical: StockScoreDetail


class SectorScore(BaseModel):
    total: float
    earnings_growth: ScoreItem
    institutional_consensus: ScoreItem
    valuation_attractiveness: ScoreItem
    policy_impact: ScoreItem
    technical_momentum: ScoreItem
    risk_adjusted_return: ScoreItem
