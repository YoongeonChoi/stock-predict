"""Index forecast engine: Monte Carlo simulation + LLM qualitative adjustment."""

import numpy as np
from datetime import datetime
from app.data import yfinance_client, cache
from app.analysis.llm_client import ask_json
from app.analysis.prompts import index_forecast_prompt
from app.models.forecast import IndexForecast, ForecastScenario
from app.config import get_settings

TRADING_DAYS_1M = 21
NUM_SIMULATIONS = 10000


async def forecast_index(
    index_ticker: str,
    index_name: str,
    economic_data: dict,
    news_summary: str,
) -> IndexForecast:
    settings = get_settings()
    cache_key = f"forecast:{index_ticker}"
    cached = await cache.get(cache_key)
    if cached:
        return IndexForecast(**cached)

    returns = await yfinance_client.get_historical_returns(index_ticker, days=60)
    quote = await yfinance_client.get_index_quote(index_ticker)
    current_price = quote.get("price", 0)

    if not returns or current_price == 0:
        return _fallback(index_ticker, index_name, current_price)

    mc_result = _monte_carlo(current_price, returns)

    system, user = index_forecast_prompt(
        index_name, current_price, mc_result, economic_data, news_summary
    )
    llm = await ask_json(system, user, temperature=0.3)

    fair_value = float(llm.get("fair_value", mc_result["base"])) if "error" not in llm else mc_result["base"]
    scenarios = []
    if "error" not in llm:
        for s in llm.get("scenarios", []):
            scenarios.append(ForecastScenario(
                name=s.get("name", ""),
                price=round(float(s.get("price", 0)), 2),
                probability=float(s.get("probability", 33)),
                description=s.get("description", ""),
            ))

    if not scenarios:
        scenarios = [
            ForecastScenario(name="Bull", price=round(mc_result["bull"], 2), probability=25,
                             description="Statistical upper band"),
            ForecastScenario(name="Base", price=round(mc_result["base"], 2), probability=50,
                             description="Most likely scenario"),
            ForecastScenario(name="Bear", price=round(mc_result["bear"], 2), probability=25,
                             description="Statistical lower band"),
        ]

    result = IndexForecast(
        index_ticker=index_ticker,
        index_name=index_name,
        current_price=round(current_price, 2),
        fair_value=round(fair_value, 2),
        scenarios=scenarios,
        confidence_note=llm.get("confidence_note", ""),
        generated_at=datetime.now().isoformat(),
    )

    await cache.set(cache_key, result.model_dump(), settings.cache_ttl_forecast)
    return result


def _monte_carlo(current: float, returns: list[float]) -> dict:
    mu = np.mean(returns)
    sigma = np.std(returns)

    rng = np.random.default_rng(42)
    simulated = rng.normal(mu, sigma, (NUM_SIMULATIONS, TRADING_DAYS_1M))
    cumulative = np.exp(simulated.cumsum(axis=1))
    final_prices = current * cumulative[:, -1]

    return {
        "bull": round(float(np.percentile(final_prices, 90)), 2),
        "base": round(float(np.percentile(final_prices, 50)), 2),
        "bear": round(float(np.percentile(final_prices, 10)), 2),
        "p25": round(float(np.percentile(final_prices, 25)), 2),
        "p75": round(float(np.percentile(final_prices, 75)), 2),
    }


def _fallback(ticker: str, name: str, price: float) -> IndexForecast:
    return IndexForecast(
        index_ticker=ticker,
        index_name=name,
        current_price=price,
        fair_value=price,
        scenarios=[
            ForecastScenario(name="Bull", price=round(price * 1.05, 2), probability=25),
            ForecastScenario(name="Base", price=price, probability=50),
            ForecastScenario(name="Bear", price=round(price * 0.95, 2), probability=25),
        ],
        confidence_note="Insufficient data for statistical forecast.",
        generated_at=datetime.now().isoformat(),
    )
