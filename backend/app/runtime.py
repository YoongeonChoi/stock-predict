"""In-memory runtime diagnostics for startup and background tasks."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Awaitable, Callable


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


_state = {
    "started_at": _utcnow(),
    "startup_tasks": [],
}
_background_jobs: dict[str, asyncio.Task] = {}


def reset_runtime_state() -> None:
    _state["started_at"] = _utcnow()
    _state["startup_tasks"] = []
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
    }


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
