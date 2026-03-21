from pydantic import BaseModel


class ArchiveEntry(BaseModel):
    id: int
    report_type: str
    country_code: str | None = None
    sector_id: str | None = None
    ticker: str | None = None
    created_at: float
    preview: str = ""


class AccuracyStats(BaseModel):
    total_predictions: int
    within_5pct: int
    accuracy_rate: float
    avg_error_pct: float
