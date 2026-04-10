from __future__ import annotations

import ctypes
import ctypes.util
import gc
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_TRIM_COOLDOWN_SECONDS = 2.0
_TRIM_MIN_PRESSURE_RATIO = 0.7
_TRIM_LOCK = threading.Lock()
_LAST_TRIM_MONOTONIC = 0.0
_TRIM_STATS: dict[str, Any] = {
    "attempts": 0,
    "successes": 0,
    "last_reason": None,
    "last_trimmed_at": None,
    "last_before_mb": None,
    "last_after_mb": None,
    "last_pressure_ratio_before": None,
    "last_pressure_ratio_after": None,
    "last_malloc_trim_applied": False,
    "last_gc_collected": 0,
    "last_cooldown_bypassed": False,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_int_file(*paths: str) -> int | None:
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _read_process_rss_bytes() -> int | None:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("VmRSS:"):
                    continue
                parts = line.split(":", 1)[1].strip().split()
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].lower() == "kb":
                    return int(parts[0]) * 1024
    except OSError:
        return None
    return None


def _get_pressure_snapshot(settings) -> dict[str, float | int | None]:
    current_bytes = _read_int_file(
        "/sys/fs/cgroup/memory.current",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    )
    limit_bytes = _read_int_file(
        "/sys/fs/cgroup/memory.max",
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    )
    rss_bytes = _read_process_rss_bytes()
    budget_bytes = limit_bytes or (max(1, int(settings.runtime_memory_budget_mb)) * 1024 * 1024)
    observed_bytes = current_bytes or rss_bytes or 0
    pressure_ratio = (observed_bytes / budget_bytes) if budget_bytes else 0.0
    return {
        "current_bytes": current_bytes,
        "rss_bytes": rss_bytes,
        "budget_bytes": budget_bytes,
        "observed_bytes": observed_bytes,
        "pressure_ratio": pressure_ratio,
    }


def _try_malloc_trim() -> bool:
    if os.name == "nt":
        return False
    libc_name = ctypes.util.find_library("c") or "libc.so.6"
    try:
        libc = ctypes.CDLL(libc_name)
        malloc_trim = getattr(libc, "malloc_trim", None)
        if malloc_trim is None:
            return False
        malloc_trim.argtypes = [ctypes.c_size_t]
        malloc_trim.restype = ctypes.c_int
        return bool(malloc_trim(0))
    except Exception:
        return False


def reset_memory_trim_state() -> None:
    global _LAST_TRIM_MONOTONIC
    with _TRIM_LOCK:
        _LAST_TRIM_MONOTONIC = 0.0
        _TRIM_STATS.update(
            {
                "attempts": 0,
                "successes": 0,
                "last_reason": None,
                "last_trimmed_at": None,
                "last_before_mb": None,
                "last_after_mb": None,
                "last_pressure_ratio_before": None,
                "last_pressure_ratio_after": None,
                "last_malloc_trim_applied": False,
                "last_gc_collected": 0,
                "last_cooldown_bypassed": False,
            }
        )


def get_memory_trim_stats() -> dict[str, Any]:
    with _TRIM_LOCK:
        return dict(_TRIM_STATS)


def get_memory_pressure_snapshot() -> dict[str, Any]:
    settings = get_settings()
    snapshot = _get_pressure_snapshot(settings)
    observed_bytes = int(snapshot.get("observed_bytes") or 0)
    resolved_budget_bytes = int(snapshot.get("budget_bytes") or 0)
    pressure_ratio = (observed_bytes / resolved_budget_bytes) if resolved_budget_bytes else 0.0
    pressure_state = "ok"
    if pressure_ratio >= 0.9:
        pressure_state = "critical"
    elif pressure_ratio >= 0.75:
        pressure_state = "warning"
    return {
        "observed_bytes": observed_bytes,
        "observed_mb": round(observed_bytes / (1024 * 1024), 2),
        "resolved_budget_bytes": resolved_budget_bytes,
        "resolved_budget_mb": round(resolved_budget_bytes / (1024 * 1024), 2) if resolved_budget_bytes else None,
        "pressure_ratio": round(pressure_ratio, 4),
        "pressure_state": pressure_state,
    }


def maybe_trim_process_memory(reason: str, *, min_pressure_ratio: float = _TRIM_MIN_PRESSURE_RATIO) -> dict[str, Any]:
    global _LAST_TRIM_MONOTONIC

    settings = get_settings()
    if not settings.startup_memory_safe_mode:
        return {"attempted": False, "trimmed": False, "skipped": "not_render_safe"}

    before = _get_pressure_snapshot(settings)
    before_ratio = float(before.get("pressure_ratio") or 0.0)
    if before_ratio < float(min_pressure_ratio):
        return {
            "attempted": False,
            "trimmed": False,
            "skipped": "below_threshold",
            "pressure_ratio": round(before_ratio, 4),
        }

    with _TRIM_LOCK:
        now = time.monotonic()
        cooldown_seconds = 0.0 if before_ratio >= 0.9 else _TRIM_COOLDOWN_SECONDS
        cooldown_remaining = cooldown_seconds - (now - _LAST_TRIM_MONOTONIC)
        if cooldown_seconds > 0 and cooldown_remaining > 0:
            return {
                "attempted": False,
                "trimmed": False,
                "skipped": "cooldown",
                "pressure_ratio": round(before_ratio, 4),
                "cooldown_remaining_seconds": round(cooldown_remaining, 2),
            }
        _LAST_TRIM_MONOTONIC = now
        _TRIM_STATS["attempts"] = int(_TRIM_STATS["attempts"]) + 1

    collected = gc.collect()
    malloc_trim_applied = _try_malloc_trim()
    after = _get_pressure_snapshot(settings)
    after_ratio = float(after.get("pressure_ratio") or 0.0)
    before_mb = round(float(before.get("observed_bytes") or 0) / (1024 * 1024), 2)
    after_mb = round(float(after.get("observed_bytes") or 0) / (1024 * 1024), 2)
    trimmed = after_mb <= before_mb

    with _TRIM_LOCK:
        if trimmed:
            _TRIM_STATS["successes"] = int(_TRIM_STATS["successes"]) + 1
        _TRIM_STATS.update(
            {
                "last_reason": reason,
                "last_trimmed_at": _utcnow(),
                "last_before_mb": before_mb,
                "last_after_mb": after_mb,
                "last_pressure_ratio_before": round(before_ratio, 4),
                "last_pressure_ratio_after": round(after_ratio, 4),
                "last_malloc_trim_applied": malloc_trim_applied,
                "last_gc_collected": int(collected),
                "last_cooldown_bypassed": cooldown_seconds == 0.0,
            }
        )

    logger.info(
        "memory trim | reason=%s before_mb=%.2f after_mb=%.2f ratio_before=%.4f ratio_after=%.4f collected=%s malloc_trim=%s",
        reason,
        before_mb,
        after_mb,
        before_ratio,
        after_ratio,
        collected,
        malloc_trim_applied,
    )
    return {
        "attempted": True,
        "trimmed": trimmed,
        "reason": reason,
        "before_mb": before_mb,
        "after_mb": after_mb,
        "pressure_ratio_before": round(before_ratio, 4),
        "pressure_ratio_after": round(after_ratio, 4),
        "malloc_trim_applied": malloc_trim_applied,
        "gc_collected": int(collected),
        "cooldown_bypassed": cooldown_seconds == 0.0,
    }
