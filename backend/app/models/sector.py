from pydantic import BaseModel
from app.models.score import SectorScore


class SectorStockItem(BaseModel):
    rank: int
    ticker: str
    name: str
    score: float
    current_price: float
    change_pct: float
    pros: list[str]
    cons: list[str]
    buy_price: float | None = None
    sell_price: float | None = None


class SectorInfo(BaseModel):
    id: str
    name: str
    country_code: str
    stock_count: int = 0


class SectorReport(BaseModel):
    sector: SectorInfo
    score: SectorScore
    summary: str
    top_stocks: list[SectorStockItem]
    correlation_matrix: dict[str, dict[str, float]] | None = None
    generated_at: str
