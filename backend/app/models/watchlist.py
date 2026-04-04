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
    resolution_note: str | None = None
    tracking_enabled: bool = False
    tracking_started_at: str | None = None
    tracking_updated_at: str | None = None
    last_prediction_at: str | None = None
    last_outlook_label: str | None = None
    last_confidence: float | None = None
