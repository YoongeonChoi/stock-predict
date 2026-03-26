"""Index forecast engine backed by the shared distribution model."""

from __future__ import annotations

from datetime import datetime
from math import exp

from app.analysis.distributional_return_engine import MODEL_VERSION, build_distributional_forecast
from app.data import cache, yfinance_client
from app.models.forecast import ForecastScenario, IndexForecast
from app.config import get_settings

TRADING_DAYS_1M = 20


def _price(reference_price: float, log_return: float) -> float:
    return round(reference_price * exp(log_return), 2) if reference_price > 0 else 0.0


async def forecast_index(
    index_ticker: str,
    index_name: str,
    economic_data: dict,
    news_summary: str,
    *,
    price_history: list[dict] | None = None,
    benchmark_history: list[dict] | None = None,
    breadth_context: dict | None = None,
    news_items: list[dict] | None = None,
    event_context: dict | None = None,
) -> IndexForecast:
    settings = get_settings()
    reference_token = str((price_history or [])[-1]["date"]) if price_history else "live"
    cache_key = f"forecast:{index_ticker}:{reference_token}:{MODEL_VERSION}"
    cached = await cache.get(cache_key)
    if cached:
        return IndexForecast(**cached)

    resolved_history = price_history or await yfinance_client.get_price_history(index_ticker, period="2y")
    if not resolved_history:
        return _fallback(index_ticker, index_name, 0.0)

    structured_news = news_items or [
        {"title": line.strip(), "published": resolved_history[-1].get("date"), "source": "news"}
        for line in str(news_summary or "").splitlines()
        if line.strip()
    ]

    distribution = build_distributional_forecast(
        price_history=resolved_history,
        benchmark_history=benchmark_history,
        macro_snapshot=economic_data or {},
        news_items=structured_news,
        event_context=event_context,
        breadth_context=breadth_context or {},
        horizons=(TRADING_DAYS_1M,),
        asset_type="index",
    )
    if distribution is None:
        current_price = float(resolved_history[-1].get("close") or 0.0)
        return _fallback(index_ticker, index_name, current_price)

    horizon = distribution.horizons[TRADING_DAYS_1M]
    result = IndexForecast(
        index_ticker=index_ticker,
        index_name=index_name,
        current_price=round(distribution.reference_price, 2),
        fair_value=_price(distribution.reference_price, horizon.q50),
        scenarios=[
            ForecastScenario(
                name="Bull",
                price=_price(distribution.reference_price, horizon.q90),
                probability=round(horizon.p_up, 1),
                description="상방 90분위 시나리오입니다.",
            ),
            ForecastScenario(
                name="Base",
                price=_price(distribution.reference_price, horizon.q50),
                probability=round(horizon.p_flat, 1),
                description="조건부 수익률 분포의 중앙값입니다.",
            ),
            ForecastScenario(
                name="Bear",
                price=_price(distribution.reference_price, horizon.q10),
                probability=round(horizon.p_down, 1),
                description="하방 10분위 시나리오입니다.",
            ),
        ],
        confidence_note=distribution.confidence_note,
        generated_at=datetime.now().isoformat(),
    )

    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_forecast)
    return result


def _fallback(ticker: str, name: str, price: float) -> IndexForecast:
    return IndexForecast(
        index_ticker=ticker,
        index_name=name,
        current_price=price,
        fair_value=price,
        scenarios=[
            ForecastScenario(name="Bull", price=round(price * 1.05, 2), probability=25.0),
            ForecastScenario(name="Base", price=price, probability=50.0),
            ForecastScenario(name="Bear", price=round(price * 0.95, 2), probability=25.0),
        ],
        confidence_note="가격 이력이 부족해 분포 예측을 수행하지 못했습니다.",
        generated_at=datetime.now().isoformat(),
    )
