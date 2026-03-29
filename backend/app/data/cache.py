"""Thin helper around Database.cache_* for ergonomic per-module usage."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

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


async def _resolve_timeout_fallback(
    timeout_fallback: Any,
):
    if timeout_fallback is None:
        raise asyncio.TimeoutError()
    value = timeout_fallback() if callable(timeout_fallback) else timeout_fallback
    if asyncio.iscoroutine(value):
        return await value
    return value


async def get_or_fetch(
    key: str,
    fetcher,
    ttl: int | None = None,
    *,
    wait_timeout: float | None = None,
    timeout_fallback: Callable[[], Any] | Callable[[], Awaitable[Any]] | None = None,
):
    cached = await get(key)
    if cached is not None:
        return cached

    in_flight = _INFLIGHT_FETCHES.get(key)
    if in_flight is not None:
        if wait_timeout is None:
            return await in_flight
        try:
            return await asyncio.wait_for(asyncio.shield(in_flight), timeout=wait_timeout)
        except asyncio.TimeoutError:
            return await _resolve_timeout_fallback(timeout_fallback)

    task = asyncio.create_task(fetcher())
    _INFLIGHT_FETCHES[key] = task
    try:
        value = await task
        if value is not None:
            await set(key, value, ttl)
        return value
    finally:
        _INFLIGHT_FETCHES.pop(key, None)
