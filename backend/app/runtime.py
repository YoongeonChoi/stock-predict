"""In-memory runtime diagnostics for startup and background tasks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


_state = {
    "started_at": _utcnow(),
    "startup_tasks": [],
}


def reset_runtime_state() -> None:
    _state["started_at"] = _utcnow()
    _state["startup_tasks"] = []


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
