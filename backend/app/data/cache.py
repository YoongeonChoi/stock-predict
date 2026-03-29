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

    async def _await_inflight(task: asyncio.Task):
        if wait_timeout is None:
            return await task
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=wait_timeout)
        except asyncio.TimeoutError:
            return await _resolve_timeout_fallback(timeout_fallback)

    in_flight = _INFLIGHT_FETCHES.get(key)
    if in_flight is not None:
        return await _await_inflight(in_flight)

    async def _fetch_and_cache():
        try:
            value = await fetcher()
            if value is not None:
                await set(key, value, ttl)
            return value
        finally:
            _INFLIGHT_FETCHES.pop(key, None)

    task = asyncio.create_task(_fetch_and_cache())
    _INFLIGHT_FETCHES[key] = task
    return await _await_inflight(task)
