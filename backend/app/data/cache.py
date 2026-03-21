"""Thin helper around Database.cache_* for ergonomic per-module usage."""

from app.database import db
from app.config import get_settings


async def get(key: str):
    return await db.cache_get(key)


async def set(key: str, value, ttl: int | None = None):
    ttl = ttl or get_settings().cache_ttl_price
    await db.cache_set(key, value, ttl)


async def get_or_fetch(key: str, fetcher, ttl: int | None = None):
    cached = await get(key)
    if cached is not None:
        return cached
    value = await fetcher()
    if value is not None:
        await set(key, value, ttl)
    return value
