from functools import lru_cache
import re

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    ecos_api_key: str = ""
    fmp_api_key: str = ""
    opendart_api_key: str = ""
    kosis_api_key: str = ""
    kosis_cpi_stats_id: str = Field(
        default="",
        validation_alias=AliasChoices("KOSIS_CPI_STATS_ID", "KOSIS_CPI_USER_STATS_ID"),
    )
    kosis_employment_stats_id: str = Field(
        default="",
        validation_alias=AliasChoices("KOSIS_EMPLOYMENT_STATS_ID", "KOSIS_EMPLOYMENT_USER_STATS_ID"),
    )
    kosis_industrial_production_stats_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "KOSIS_INDUSTRIAL_PRODUCTION_STATS_ID",
            "KOSIS_INDUSTRIAL_PRODUCTION_USER_STATS_ID",
        ),
    )
    naver_client_id: str = ""
    naver_client_secret: str = ""

    db_path: str = "data/stock_predict.db"
    supabase_url: str = ""
    supabase_server_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_SERVER_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SECRET_KEY",
        ),
    )

    frontend_url: str = "http://localhost:3000"
    frontend_urls: str = ""
    frontend_origin_regex: str = ""

    startup_prediction_accuracy_refresh: bool = True
    startup_prediction_accuracy_refresh_timeout: int = 20
    startup_research_archive_sync: bool = True
    startup_research_archive_sync_timeout: int = 35

    cache_ttl_price: int = 900
    cache_ttl_chart: int = 3600
    cache_ttl_fundamentals: int = 86400
    cache_ttl_economic: int = 86400
    cache_ttl_news: int = 3600
    cache_ttl_fmp: int = 3600
    cache_ttl_report: int = 21600
    cache_ttl_forecast: int = 21600
    cache_ttl_fear_greed: int = 3600

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def cors_origins(self) -> list[str]:
        candidates = [self.frontend_url, "http://localhost:3000"]
        if self.frontend_urls:
            candidates.extend(re.split(r"[\n,]", self.frontend_urls))

        origins: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            origin = candidate.strip().rstrip("/")
            if not origin or origin in seen:
                continue
            seen.add(origin)
            origins.append(origin)
        return origins

    @property
    def cors_origin_regex(self) -> str | None:
        value = self.frontend_origin_regex.strip()
        return value or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
