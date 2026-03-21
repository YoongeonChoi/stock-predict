from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    fred_api_key: str = ""
    ecos_api_key: str = ""
    fmp_api_key: str = ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
