from pydantic import BaseModel


class WatchlistItem(BaseModel):
    id: int
    ticker: str
    country_code: str
    added_at: float
    name: str | None = None
    current_price: float | None = None
    change_pct: float | None = None
    score_total: float | None = None
