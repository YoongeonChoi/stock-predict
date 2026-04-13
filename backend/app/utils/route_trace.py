from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


FAILURE_CLASSES: tuple[str, ...] = (
    "shell_blocked",
    "quick_timeout",
    "full_timeout",
    "stale_served",
    "upstream_unavailable",
    "session_recovery_failed",
    "panel_fetch_failed",
    "auth_required",
    "write_failed",
    "contract_mismatch",
)


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


def infer_failure_class(
    *,
    request_phase: str,
    payload: dict[str, Any] | None = None,
    failure_class: str | None = None,
    fallback_reason: str | None = None,
    served_state: str | None = None,
) -> str | None:
    if failure_class:
        return str(failure_class)

    resolved_fallback_reason = infer_fallback_reason(payload=payload, fallback_reason=fallback_reason)
    resolved_served_state = infer_served_state(payload=payload, served_state=served_state)
    lowered_reason = str(resolved_fallback_reason or "").lower()
    normalized_phase = str(request_phase or "").lower()

    if resolved_served_state == "stale":
        return "stale_served"
    if any(token in lowered_reason for token in ("timeout", "timed_out", "time_budget")):
        return "full_timeout" if normalized_phase == "full" else "quick_timeout"
    if any(token in lowered_reason for token in ("upstream", "unavailable", "provider")):
        return "upstream_unavailable"
    if "auth" in lowered_reason:
        return "auth_required"
    return None


def infer_recovered(
    *,
    failure_class: str | None,
    recovered: bool | None = None,
) -> bool:
    if recovered is not None:
        return bool(recovered)
    if failure_class in {"quick_timeout", "full_timeout", "stale_served", "upstream_unavailable"}:
        return True
    return False


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
    operation_kind: str = "public-read",
    timeout_budget_ms: float | None = None,
    upstream_source: str = "internal",
    payload: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
    served_state: str | None = None,
    failure_class: str | None = None,
    panel_key: str | None = None,
    dependency_key: str | None = None,
    recovered: bool | None = None,
    cold_start_suspected: bool | None = None,
) -> dict[str, Any]:
    resolved_served_state = infer_served_state(payload=payload, served_state=served_state)
    resolved_fallback_reason = infer_fallback_reason(payload=payload, fallback_reason=fallback_reason)
    resolved_failure_class = infer_failure_class(
        request_phase=request_phase,
        payload=payload,
        failure_class=failure_class,
        fallback_reason=resolved_fallback_reason,
        served_state=resolved_served_state,
    )
    resolved_cold_start = (
        infer_cold_start_suspected(
            cache_state=cache_state,
            elapsed_ms=elapsed_ms,
            timeout_budget_ms=timeout_budget_ms,
        )
        if cold_start_suspected is None
        else cold_start_suspected
    )
    resolved_recovered = infer_recovered(
        failure_class=resolved_failure_class,
        recovered=recovered,
    )
    return {
        "route_key": route_key,
        "request_phase": request_phase,
        "operation_kind": operation_kind,
        "cache_state": cache_state,
        "cold_start_suspected": resolved_cold_start,
        "upstream_source": upstream_source,
        "elapsed_ms": round(float(elapsed_ms), 1),
        "timeout_budget_ms": round(float(timeout_budget_ms), 1) if timeout_budget_ms is not None else None,
        "fallback_reason": resolved_fallback_reason,
        "served_state": resolved_served_state,
        "failure_class": resolved_failure_class,
        "panel_key": panel_key,
        "dependency_key": dependency_key,
        "recovered": resolved_recovered,
        "recorded_at": _utcnow(),
    }
