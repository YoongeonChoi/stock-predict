from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_served_state(
    *,
    payload: dict[str, Any] | None = None,
    served_state: str | None = None,
) -> str:
    if served_state:
        return served_state
    if not payload:
        return "fresh"
    if payload.get("partial"):
        return "partial"
    return "fresh"


def infer_fallback_reason(
    *,
    payload: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> str | None:
    if fallback_reason:
        return fallback_reason
    if not payload:
        return None
    value = payload.get("fallback_reason")
    return str(value) if value else None


def infer_cold_start_suspected(
    *,
    cache_state: str,
    elapsed_ms: float,
    timeout_budget_ms: float | None = None,
) -> bool:
    if cache_state == "miss" and elapsed_ms >= 6000:
        return True
    if timeout_budget_ms and elapsed_ms >= timeout_budget_ms * 0.85:
        return True
    return False


def build_route_trace(
    *,
    route_key: str,
    request_phase: str,
    cache_state: str,
    elapsed_ms: float,
    timeout_budget_ms: float | None = None,
    upstream_source: str = "internal",
    payload: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
    served_state: str | None = None,
    cold_start_suspected: bool | None = None,
) -> dict[str, Any]:
    resolved_served_state = infer_served_state(payload=payload, served_state=served_state)
    resolved_fallback_reason = infer_fallback_reason(payload=payload, fallback_reason=fallback_reason)
    resolved_cold_start = (
        infer_cold_start_suspected(
            cache_state=cache_state,
            elapsed_ms=elapsed_ms,
            timeout_budget_ms=timeout_budget_ms,
        )
        if cold_start_suspected is None
        else cold_start_suspected
    )
    return {
        "route_key": route_key,
        "request_phase": request_phase,
        "cache_state": cache_state,
        "cold_start_suspected": resolved_cold_start,
        "upstream_source": upstream_source,
        "elapsed_ms": round(float(elapsed_ms), 1),
        "timeout_budget_ms": round(float(timeout_budget_ms), 1) if timeout_budget_ms is not None else None,
        "fallback_reason": resolved_fallback_reason,
        "served_state": resolved_served_state,
        "recorded_at": _utcnow(),
    }

