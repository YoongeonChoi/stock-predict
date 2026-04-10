"""Thin helper around Database.cache_* for ergonomic per-module usage."""

from __future__ import annotations

import asyncio
import copy
import fnmatch
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import get_settings
from app.database import db

_INFLIGHT_FETCHES: dict[str, asyncio.Task] = {}
_MEMORY_CACHE: dict[str, tuple[float, Any, int]] = {}
_MEMORY_CACHE_TOTAL_ESTIMATED_BYTES = 0
_MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES = 0


def _estimate_value_size_bytes(value: Any) -> int:
    try:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        return len(payload.encode("utf-8"))
    except Exception:
        return len(repr(value).encode("utf-8", errors="ignore"))


def _resolve_memory_limits() -> tuple[int, int, int]:
    settings = get_settings()
    max_entries = max(
        1,
        int(
            getattr(
                settings,
                "effective_cache_memory_max_entries",
                getattr(settings, "cache_memory_max_entries", 256),
            )
        ),
    )
    max_bytes = max(
        1,
        int(
            getattr(
                settings,
                "effective_cache_memory_max_mb",
                getattr(settings, "cache_memory_max_mb", 64),
            )
        ),
    ) * 1024 * 1024
    max_entry_bytes = max(
        1,
        int(
            getattr(
                settings,
                "effective_cache_memory_max_entry_mb",
                getattr(settings, "cache_memory_max_entry_mb", 8),
            )
        ),
    ) * 1024 * 1024
    return max_entries, max_bytes, max_entry_bytes


def _memory_pop(key: str):
    global _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES
    entry = _MEMORY_CACHE.pop(key, None)
    if entry is None:
        return None
    _, value, estimated_bytes = entry
    _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES = max(
        0,
        _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES - max(int(estimated_bytes), 0),
    )
    return value


def _prune_expired_memory_entries() -> None:
    now = time.time()
    for key, (expires_at, _, _) in list(_MEMORY_CACHE.items()):
        if expires_at <= now:
            _memory_pop(key)


def _enforce_memory_limits() -> None:
    max_entries, max_bytes, _ = _resolve_memory_limits()

    _prune_expired_memory_entries()

    while len(_MEMORY_CACHE) > max_entries or _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES > max_bytes:
        oldest_key = next(iter(_MEMORY_CACHE), None)
        if oldest_key is None:
            break
        _memory_pop(oldest_key)


def _memory_get(key: str):
    entry = _MEMORY_CACHE.get(key)
    if entry is None:
        return None
    expires_at, value, _ = entry
    if expires_at <= time.time():
        _memory_pop(key)
        return None
    return copy.deepcopy(value)


def _memory_set(key: str, value: Any, ttl: int):
    global _MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES
    global _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES
    if ttl <= 0:
        _memory_pop(key)
        return
    _, _, max_entry_bytes = _resolve_memory_limits()
    estimated_bytes = _estimate_value_size_bytes(value)
    if estimated_bytes > max_entry_bytes:
        _memory_pop(key)
        _MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES += 1
        return
    payload = copy.deepcopy(value)
    _memory_pop(key)
    _MEMORY_CACHE[key] = (time.time() + ttl, payload, estimated_bytes)
    _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES += estimated_bytes
    _enforce_memory_limits()


def _memory_invalidate(pattern: str):
    glob_pattern = pattern.replace("%", "*").replace("_", "?")
    for key in list(_MEMORY_CACHE):
        if fnmatch.fnmatch(key, glob_pattern):
            _memory_pop(key)


def reset_memory_cache_state() -> None:
    global _MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES
    global _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES
    _MEMORY_CACHE.clear()
    _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES = 0
    _MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES = 0
    _INFLIGHT_FETCHES.clear()


def get_memory_cache_stats() -> dict[str, Any]:
    _prune_expired_memory_entries()
    max_entries, max_bytes, max_entry_bytes = _resolve_memory_limits()
    largest_entries = sorted(
        (
            {
                "key": key,
                "estimated_bytes": estimated_bytes,
                "ttl_seconds": max(0.0, round(expires_at - time.time(), 2)),
            }
            for key, (expires_at, _, estimated_bytes) in _MEMORY_CACHE.items()
        ),
        key=lambda item: int(item["estimated_bytes"]),
        reverse=True,
    )[:5]
    return {
        "entry_count": len(_MEMORY_CACHE),
        "estimated_bytes": _MEMORY_CACHE_TOTAL_ESTIMATED_BYTES,
        "entry_limit": max_entries,
        "estimated_bytes_limit": max_bytes,
        "estimated_entry_bytes_limit": max_entry_bytes,
        "estimated_utilization_ratio": round(_MEMORY_CACHE_TOTAL_ESTIMATED_BYTES / max_bytes, 4) if max_bytes else 0.0,
        "inflight_fetches": len(_INFLIGHT_FETCHES),
        "skipped_oversized_writes": _MEMORY_CACHE_SKIPPED_OVERSIZED_WRITES,
        "largest_entries": largest_entries,
    }


async def get(key: str):
    cached = _memory_get(key)
    if cached is not None:
        return cached
    return await db.cache_get(key)


async def set(key: str, value, ttl: int | None = None):
    ttl = ttl or get_settings().cache_ttl_price
    _memory_set(key, value, ttl)
    await db.cache_set(key, value, ttl)


async def invalidate(pattern: str):
    _memory_invalidate(pattern)
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
