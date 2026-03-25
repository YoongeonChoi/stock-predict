"""Naver Search API client for Korean-market news."""

from __future__ import annotations

import re
from datetime import datetime

import httpx

from app.config import get_settings
from app.data import cache
from app.errors import SP_2007

BASE_URL = "https://openapi.naver.com/v1/search/news.json"


async def search_news(query: str, max_results: int = 10, sort: str = "date") -> list[dict]:
    settings = get_settings()
    if not (settings.naver_client_id and settings.naver_client_secret):
        return []

    async def _fetch():
        headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        }
        params = {
            "query": query,
            "display": max(1, min(max_results, 100)),
            "start": 1,
            "sort": sort,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(BASE_URL, headers=headers, params=params)
                response.raise_for_status()
                items = response.json().get("items", [])
        except Exception as exc:
            SP_2007(str(exc)[:150]).log("warning")
            return []

        results: list[dict] = []
        for item in items[:max_results]:
            results.append(
                {
                    "title": _clean(item.get("title", "")),
                    "source": "Naver Search",
                    "url": item.get("originallink") or item.get("link") or "",
                    "published": _normalize_date(item.get("pubDate", "")),
                    "description": _clean(item.get("description", "")),
                }
            )
        return results

    return await cache.get_or_fetch(
        f"naver_news:{query[:80]}:{max_results}:{sort}",
        _fetch,
        settings.cache_ttl_news,
    )


def _clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")
        return parsed.isoformat()
    except ValueError:
        return value
