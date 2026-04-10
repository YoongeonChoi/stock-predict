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
    render_environment: bool = Field(
        default=False,
        validation_alias=AliasChoices("RENDER", "IS_RENDER"),
    )
    render_service_name: str = ""
    render_instance_id: str = ""

    startup_prediction_accuracy_refresh: bool = True
    startup_prediction_accuracy_refresh_timeout: int = 20
    startup_prediction_accuracy_refresh_on_render: bool = True
    startup_research_archive_sync: bool = True
    startup_research_archive_sync_timeout: int = 35
    startup_learned_fusion_refresh: bool = True
    startup_learned_fusion_refresh_timeout: int = 25
    startup_market_opportunity_prewarm: bool = True
    startup_market_opportunity_prewarm_timeout: int = 180
    startup_background_task_concurrency: int = 3
    startup_allow_heavy_render_jobs: bool = False
    stock_detail_background_refresh: bool = True
    stock_detail_allow_render_background_refresh: bool = False

    cache_ttl_price: int = 900
    cache_ttl_chart: int = 3600
    cache_ttl_fundamentals: int = 86400
    cache_ttl_economic: int = 86400
    cache_ttl_news: int = 3600
    cache_ttl_fmp: int = 3600
    cache_ttl_report: int = 21600
    cache_ttl_forecast: int = 21600
    cache_ttl_fear_greed: int = 3600
    cache_memory_max_entries: int = 256
    cache_memory_max_mb: int = 64
    cache_memory_max_entry_mb: int = 8
    diagnostics_probe_timeout_seconds: int = 3
    runtime_memory_budget_mb: int = 500

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

    @property
    def startup_memory_safe_mode(self) -> bool:
        on_render = self.render_environment or bool(self.render_service_name.strip()) or bool(self.render_instance_id.strip())
        return on_render and not self.startup_allow_heavy_render_jobs

    @property
    def effective_startup_prediction_accuracy_refresh(self) -> bool:
        if self.startup_memory_safe_mode:
            return (
                self.startup_prediction_accuracy_refresh
                and self.startup_prediction_accuracy_refresh_on_render
            )
        return self.startup_prediction_accuracy_refresh

    @property
    def effective_startup_prediction_accuracy_refresh_timeout(self) -> int:
        if self.startup_memory_safe_mode:
            return min(self.startup_prediction_accuracy_refresh_timeout, 8)
        return self.startup_prediction_accuracy_refresh_timeout

    @property
    def effective_startup_prediction_accuracy_refresh_limit(self) -> int:
        if self.startup_memory_safe_mode:
            return 25
        return 100

    @property
    def effective_startup_learned_fusion_refresh(self) -> bool:
        if self.startup_memory_safe_mode:
            return False
        return self.startup_learned_fusion_refresh

    @property
    def effective_startup_research_archive_sync(self) -> bool:
        if self.startup_memory_safe_mode:
            return False
        return self.startup_research_archive_sync

    @property
    def effective_startup_market_opportunity_prewarm(self) -> bool:
        if self.startup_memory_safe_mode:
            return False
        return self.startup_market_opportunity_prewarm

    @property
    def effective_startup_market_opportunity_prewarm_timeout(self) -> int:
        if self.startup_memory_safe_mode:
            return min(self.startup_market_opportunity_prewarm_timeout, 45)
        return self.startup_market_opportunity_prewarm_timeout

    @property
    def effective_startup_background_task_concurrency(self) -> int:
        if self.startup_memory_safe_mode:
            return 1
        return max(1, int(self.startup_background_task_concurrency))

    @property
    def effective_cache_memory_max_entries(self) -> int:
        configured = max(1, int(self.cache_memory_max_entries))
        if self.startup_memory_safe_mode:
            return min(configured, 96)
        return configured

    @property
    def effective_cache_memory_max_mb(self) -> int:
        configured = max(1, int(self.cache_memory_max_mb))
        if self.startup_memory_safe_mode:
            return min(configured, 24)
        return configured

    @property
    def effective_cache_memory_max_entry_mb(self) -> int:
        configured = max(1, int(self.cache_memory_max_entry_mb))
        if self.startup_memory_safe_mode:
            return min(configured, 2)
        return configured

    @property
    def effective_diagnostics_probe_timeout_seconds(self) -> int:
        configured = max(1, int(self.diagnostics_probe_timeout_seconds))
        if self.startup_memory_safe_mode:
            return min(configured, 2)
        return configured

    @property
    def effective_stock_detail_background_refresh(self) -> bool:
        if not self.stock_detail_background_refresh:
            return False
        if self.startup_memory_safe_mode and not self.stock_detail_allow_render_background_refresh:
            return False
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()
