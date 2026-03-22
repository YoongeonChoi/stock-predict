"""Thin helper around Database.cache_* for ergonomic per-module usage."""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.database import db

_INFLIGHT_FETCHES: dict[str, asyncio.Task] = {}


async def get(key: str):
    return await db.cache_get(key)


async def set(key: str, value, ttl: int | None = None):
    ttl = ttl or get_settings().cache_ttl_price
    await db.cache_set(key, value, ttl)


async def invalidate(pattern: str):
    await db.cache_invalidate(pattern)


async def get_or_fetch(key: str, fetcher, ttl: int | None = None):
    cached = await get(key)
    if cached is not None:
        return cached

    in_flight = _INFLIGHT_FETCHES.get(key)
    if in_flight is not None:
        return await in_flight

    task = asyncio.create_task(fetcher())
    _INFLIGHT_FETCHES[key] = task
    try:
        value = await task
        if value is not None:
            await set(key, value, ttl)
        return value
    finally:
        _INFLIGHT_FETCHES.pop(key, None)
