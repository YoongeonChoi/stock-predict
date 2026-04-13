"""In-memory runtime diagnostics for startup and background tasks."""

from __future__ import annotations

import asyncio
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from typing import Awaitable, Callable


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


_state = {
    "started_at": _utcnow(),
    "startup_tasks": [],
    "route_stability": {},
}
_background_jobs: dict[str, asyncio.Task] = {}
_ROUTE_LATENCY_WINDOW = 64


def _build_route_state() -> dict:
    return {
        "total_requests": 0,
        "success_count": 0,
        "error_count": 0,
        "degraded_count": 0,
        "fallback_served_count": 0,
        "stale_served_count": 0,
        "cold_start_count": 0,
        "cold_failure_count": 0,
        "first_usable_latencies": deque(maxlen=_ROUTE_LATENCY_WINDOW),
        "phase_counts": {"shell": 0, "quick": 0, "full": 0},
        "cache_counts": {"memory_hit": 0, "sqlite_hit": 0, "miss": 0},
        "last_fallback_reason": None,
        "last_upstream_source": None,
        "last_served_state": None,
        "last_elapsed_ms": None,
        "last_updated_at": None,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _percentile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def reset_runtime_state() -> None:
    _state["started_at"] = _utcnow()
    _state["startup_tasks"] = []
    _state["route_stability"] = {}
    for name, task in list(_background_jobs.items()):
        if not task.done():
            task.cancel()
        _background_jobs.pop(name, None)


def upsert_startup_task(name: str, status: str, detail: str) -> None:
    task = {
        "name": name,
        "status": status,
        "detail": detail,
        "updated_at": _utcnow(),
    }
    for index, current in enumerate(_state["startup_tasks"]):
        if current["name"] == name:
            _state["startup_tasks"][index] = task
            return
    _state["startup_tasks"].append(task)


def get_runtime_state() -> dict:
    tasks = deepcopy(_state["startup_tasks"])
    statuses = {task["status"] for task in tasks}
    overall = "ok"
    if "error" in statuses or "warning" in statuses:
        overall = "degraded"
    elif "running" in statuses or "queued" in statuses:
        overall = "starting"
    return {
        "started_at": _state["started_at"],
        "status": overall,
        "startup_tasks": tasks,
        "route_stability": get_route_stability(),
    }


def record_route_observation(route: str, trace: dict | None, *, success: bool = True) -> None:
    if not route or not trace:
        return

    current = _state["route_stability"].setdefault(route, _build_route_state())
    current["total_requests"] += 1
    if success:
        current["success_count"] += 1
    else:
        current["error_count"] += 1

    request_phase = str(trace.get("request_phase") or "").strip().lower()
    if request_phase in current["phase_counts"]:
        current["phase_counts"][request_phase] += 1

    cache_state = str(trace.get("cache_state") or "").strip().lower()
    if cache_state in current["cache_counts"]:
        current["cache_counts"][cache_state] += 1

    served_state = str(trace.get("served_state") or "").strip().lower()
    if served_state == "degraded":
        current["degraded_count"] += 1
    if served_state == "stale":
        current["stale_served_count"] += 1

    fallback_reason = trace.get("fallback_reason")
    if fallback_reason:
        current["fallback_served_count"] += 1
        current["last_fallback_reason"] = fallback_reason

    cold_start_suspected = bool(trace.get("cold_start_suspected"))
    if cold_start_suspected:
        current["cold_start_count"] += 1
        if not success or served_state == "degraded":
            current["cold_failure_count"] += 1

    elapsed_ms = trace.get("elapsed_ms")
    if isinstance(elapsed_ms, (int, float)):
        current["last_elapsed_ms"] = int(elapsed_ms)
        if success and served_state in {"fresh", "partial", "stale"}:
            current["first_usable_latencies"].append(int(elapsed_ms))

    upstream_source = trace.get("upstream_source")
    if upstream_source:
        current["last_upstream_source"] = upstream_source
    if served_state:
        current["last_served_state"] = served_state
    current["last_updated_at"] = _utcnow()


def get_route_stability() -> list[dict]:
    summaries: list[dict] = []
    for route, current in _state["route_stability"].items():
        total_requests = int(current.get("total_requests") or 0)
        first_usable_latencies = list(current.get("first_usable_latencies") or [])
        summaries.append(
            {
                "route": route,
                "total_requests": total_requests,
                "success_count": int(current.get("success_count") or 0),
                "error_count": int(current.get("error_count") or 0),
                "degraded_count": int(current.get("degraded_count") or 0),
                "fallback_served_count": int(current.get("fallback_served_count") or 0),
                "stale_served_count": int(current.get("stale_served_count") or 0),
                "cold_start_count": int(current.get("cold_start_count") or 0),
                "cold_failure_count": int(current.get("cold_failure_count") or 0),
                "first_usable_p50_ms": _percentile(first_usable_latencies, 0.50),
                "first_usable_p95_ms": _percentile(first_usable_latencies, 0.95),
                "degraded_rate": _safe_rate(int(current.get("degraded_count") or 0), total_requests),
                "fallback_served_rate": _safe_rate(int(current.get("fallback_served_count") or 0), total_requests),
                "stale_served_rate": _safe_rate(int(current.get("stale_served_count") or 0), total_requests),
                "cold_failure_rate": _safe_rate(int(current.get("cold_failure_count") or 0), int(current.get("cold_start_count") or 0)),
                "phase_counts": deepcopy(current.get("phase_counts") or {}),
                "cache_counts": deepcopy(current.get("cache_counts") or {}),
                "last_fallback_reason": current.get("last_fallback_reason"),
                "last_upstream_source": current.get("last_upstream_source"),
                "last_served_state": current.get("last_served_state"),
                "last_elapsed_ms": current.get("last_elapsed_ms"),
                "last_updated_at": current.get("last_updated_at"),
            }
        )
    return sorted(summaries, key=lambda item: item["route"])


def get_or_create_background_job(
    name: str,
    job_factory: Callable[[], Awaitable[object]],
) -> tuple[asyncio.Task, bool]:
    existing = _background_jobs.get(name)
    if existing is not None and not existing.done():
        return existing, False

    task = asyncio.create_task(job_factory())
    _background_jobs[name] = task

    def _cleanup(done_task: asyncio.Task) -> None:
        if _background_jobs.get(name) is done_task:
            _background_jobs.pop(name, None)

    task.add_done_callback(_cleanup)
    return task, True
