"""Google News RSS aggregation for Korean-market news."""

import asyncio
import re
from urllib.parse import quote

import feedparser

from app.config import get_settings
from app.data import cache
from app.utils.async_tools import gather_limited

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"

LOCALE_MAP = {
    "KR": {"hl": "ko", "gl": "KR", "ceid": "KR:ko"},
}


async def search_news(
    query: str, country_code: str = "KR", max_results: int = 15
) -> list[dict]:
    settings = get_settings()
    locale = LOCALE_MAP["KR"]

    async def _fetch():
        def _sync():
            url = GOOGLE_NEWS_RSS.format(
                query=quote(query), hl=locale["hl"], gl=locale["gl"], ceid=locale["ceid"]
            )
            feed = feedparser.parse(url)
            results = []
            for entry in feed.entries[:max_results]:
                source = ""
                if hasattr(entry, "source"):
                    source = entry.source.get("title", "")
                elif " - " in entry.get("title", ""):
                    source = entry["title"].rsplit(" - ", 1)[-1]
                results.append({
                    "title": _clean(entry.get("title", "")),
                    "source": source,
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
            return results

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"news:{country_code}:{query[:60]}", _fetch, settings.cache_ttl_news
    )


async def get_institution_news(
    institution: str, country_code: str, extra_keywords: str = ""
) -> list[dict]:
    kw = f"{institution} {extra_keywords}".strip()
    return await search_news(kw, country_code, max_results=10)


async def get_market_news(country_code: str) -> list[dict]:
    del country_code
    return await search_news("한국 주식시장 전망 증시", "KR", max_results=20)


async def get_all_institution_news(
    institutions: list[str], country_code: str
) -> dict[str, list[dict]]:
    async def _fetch(institution: str):
        articles = await get_institution_news(institution, country_code, "outlook research forecast")
        return institution, articles

    result: dict[str, list[dict]] = {}
    fetched = await gather_limited(institutions, _fetch, limit=4)
    for item in fetched:
        if isinstance(item, Exception):
            continue
        institution, articles = item
        result[institution] = articles
    return result


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
