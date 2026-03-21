"""News sentiment analysis using LLM."""

from app.analysis.llm_client import ask_json
from app.analysis.prompts import sentiment_prompt
from app.data import cache
from app.config import get_settings


async def analyze_sentiment(headlines: list[str]) -> float:
    """Return sentiment score 0.0 (very negative) to 1.0 (very positive)."""
    if not headlines:
        return 0.5

    cache_key = f"sentiment:{hash(tuple(headlines[:20]))}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached.get("score", 0.5)

    system, user = sentiment_prompt(headlines)
    result = await ask_json(system, user, temperature=0.2)
    score = float(result.get("score", 0.5))
    score = max(0.0, min(1.0, score))

    await cache.set(cache_key, {"score": score}, get_settings().cache_ttl_news)
    return score


async def get_news_sentiment_for_country(news: list[dict]) -> float:
    headlines = [n.get("title", "") for n in news if n.get("title")]
    return await analyze_sentiment(headlines)
