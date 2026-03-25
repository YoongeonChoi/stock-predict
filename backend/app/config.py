from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    ecos_api_key: str = ""
    fmp_api_key: str = ""
    opendart_api_key: str = ""
    kosis_api_key: str = ""
    kosis_cpi_user_stats_id: str = ""
    kosis_employment_user_stats_id: str = ""
    kosis_industrial_production_user_stats_id: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""

    db_path: str = "data/stock_predict.db"

    frontend_url: str = "http://localhost:3000"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
