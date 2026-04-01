from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
from statistics import median
from typing import Any


_MAX_ROUTE_TRACES = 240
_MAX_FRONTEND_EVENTS = 480

_route_traces: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_ROUTE_TRACES))
_frontend_events: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_FRONTEND_EVENTS))


def reset_route_stability_state() -> None:
    _route_traces.clear()
    _frontend_events.clear()


def record_route_trace(route_key: str, trace: dict[str, Any]) -> None:
    _route_traces[route_key].append(deepcopy(trace))


def record_frontend_event(
    *,
    route: str,
    event: str,
    status: str = "ok",
    panel: str | None = None,
    detail: str | None = None,
    timeout_ms: int | None = None,
    occurred_at: str | None = None,
) -> None:
    _frontend_events[route].append(
        {
            "route": route,
            "event": event,
            "status": status,
            "panel": panel,
            "detail": detail,
            "timeout_ms": timeout_ms,
            "occurred_at": occurred_at,
        }
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return float(ordered[rank])


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _phase_mix(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    return dict(sorted(counts.items()))


def get_route_stability_summary() -> dict[str, Any]:
    route_rows: list[dict[str, Any]] = []
    all_elapsed: list[float] = []
    fallback_count = 0
    stale_count = 0
    partial_count = 0
    degraded_count = 0
    cold_count = 0
    total_count = 0

    for route_key, queue in sorted(_route_traces.items()):
        rows = list(queue)
        if not rows:
            continue
        elapsed_values = [float(row.get("elapsed_ms") or 0.0) for row in rows]
        served_states = Counter(str(row.get("served_state") or "fresh") for row in rows)
        request_phase_mix = _phase_mix(rows, "request_phase")
        cache_state_mix = _phase_mix(rows, "cache_state")
        fallback_served = sum(1 for row in rows if row.get("fallback_reason"))
        cold_suspected = sum(1 for row in rows if bool(row.get("cold_start_suspected")))

        total = len(rows)
        total_count += total
        all_elapsed.extend(elapsed_values)
        fallback_count += fallback_served
        stale_count += served_states.get("stale", 0)
        partial_count += served_states.get("partial", 0)
        degraded_count += served_states.get("degraded", 0)
        cold_count += cold_suspected

        route_rows.append(
            {
                "route": route_key,
                "total": total,
                "p50_elapsed_ms": round(median(elapsed_values), 1),
                "p95_elapsed_ms": round(_percentile(elapsed_values, 0.95), 1),
                "fallback_served_rate": _rate(fallback_served, total),
                "partial_rate": _rate(served_states.get("partial", 0), total),
                "stale_rate": _rate(served_states.get("stale", 0), total),
                "degraded_rate": _rate(served_states.get("degraded", 0), total),
                "cold_start_suspected_rate": _rate(cold_suspected, total),
                "request_phase_mix": request_phase_mix,
                "cache_state_mix": cache_state_mix,
            }
        )

    hydration_by_route: list[dict[str, Any]] = []
    session_by_route: list[dict[str, Any]] = []
    blank_events = 0
    error_only_events = 0
    hydration_events = 0
    hydration_failures = 0
    session_events = 0
    session_failures = 0

    for route, queue in sorted(_frontend_events.items()):
        rows = list(queue)
        if not rows:
            continue
        hydration_total = sum(1 for row in rows if str(row.get("event", "")).startswith("hydration_"))
        hydration_failed = sum(
            1
            for row in rows
            if row.get("event") in {"hydration_refetch_timeout", "panel_degraded"}
        )
        session_total = sum(1 for row in rows if row.get("event") == "session_recovery_attempt")
        session_failed = sum(1 for row in rows if row.get("event") == "session_recovery_failed")
        blank_count = sum(1 for row in rows if row.get("event") == "blank_screen")
        error_only_count = sum(1 for row in rows if row.get("event") == "error_only_screen")

        hydration_events += hydration_total
        hydration_failures += hydration_failed
        session_events += session_total
        session_failures += session_failed
        blank_events += blank_count
        error_only_events += error_only_count

        if hydration_total or hydration_failed:
            hydration_by_route.append(
                {
                    "route": route,
                    "total": hydration_total,
                    "failure_count": hydration_failed,
                    "failure_rate": _rate(hydration_failed, hydration_total),
                }
            )
        if session_total or session_failed:
            session_by_route.append(
                {
                    "route": route,
                    "total": session_total,
                    "failure_count": session_failed,
                    "failure_rate": _rate(session_failed, session_total),
                }
            )

    return {
        "routes": route_rows,
        "first_usable_metrics": {
            "tracked_routes": len(route_rows),
            "total_requests": total_count,
            "p50_elapsed_ms": round(median(all_elapsed), 1) if all_elapsed else 0.0,
            "p95_elapsed_ms": round(_percentile(all_elapsed, 0.95), 1) if all_elapsed else 0.0,
            "fallback_served_rate": _rate(fallback_count, total_count),
            "stale_served_rate": _rate(stale_count, total_count),
            "first_request_cold_failure_rate": _rate(cold_count, total_count),
            "blank_screen_rate": _rate(blank_events, max(blank_events + total_count, 1)),
            "error_only_screen_rate": _rate(error_only_events, max(error_only_events + total_count, 1)),
        },
        "hydration_failure_summary": {
            "tracked": bool(_frontend_events),
            "total": hydration_events,
            "failure_count": hydration_failures,
            "failure_rate": _rate(hydration_failures, hydration_events),
            "by_route": hydration_by_route,
        },
        "session_recovery_summary": {
            "tracked": bool(_frontend_events),
            "total": session_events,
            "failure_count": session_failures,
            "failure_rate": _rate(session_failures, session_events),
            "by_route": session_by_route,
        },
    }

