from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services import route_stability_service
from app.utils.route_trace import build_route_trace


class RouteStabilityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        route_stability_service.reset_route_stability_state()

    def test_route_stability_summary_tracks_rates_and_percentiles(self) -> None:
        route_stability_service.record_route_trace(
            "stock_detail",
            build_route_trace(
                route_key="stock_detail",
                request_phase="quick",
                cache_state="sqlite_hit",
                elapsed_ms=3200,
                timeout_budget_ms=12000,
                fallback_reason="stock_quick_detail",
                served_state="partial",
            ),
        )
        route_stability_service.record_route_trace(
            "stock_detail",
            build_route_trace(
                route_key="stock_detail",
                request_phase="full",
                cache_state="miss",
                elapsed_ms=8400,
                timeout_budget_ms=12000,
                served_state="fresh",
            ),
        )
        route_stability_service.record_route_trace(
            "stock_detail",
            build_route_trace(
                route_key="stock_detail",
                request_phase="full",
                cache_state="sqlite_hit",
                elapsed_ms=2100,
                timeout_budget_ms=12000,
                served_state="stale",
            ),
        )

        summary = route_stability_service.get_route_stability_summary()
        self.assertEqual(summary["first_usable_metrics"]["tracked_routes"], 1)
        self.assertEqual(summary["first_usable_metrics"]["total_requests"], 3)
        self.assertGreater(summary["first_usable_metrics"]["p95_elapsed_ms"], 8000)

        stock_row = summary["routes"][0]
        self.assertEqual(stock_row["route"], "stock_detail")
        self.assertEqual(stock_row["request_phase_mix"]["full"], 2)
        self.assertEqual(stock_row["cache_state_mix"]["sqlite_hit"], 2)
        self.assertGreater(stock_row["fallback_served_rate"], 0)
        self.assertGreater(stock_row["stale_rate"], 0)

    def test_diagnostics_event_updates_hydration_and_session_summary(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/diagnostics/event",
                json={
                    "route": "/portfolio",
                    "event": "panel_degraded",
                    "status": "warning",
                    "panel": "conditional_recommendation",
                    "detail": "조건 추천 지연",
                },
            )
            self.assertEqual(response.status_code, 200)
            response = client.post(
                "/api/diagnostics/event",
                json={
                    "route": "/settings",
                    "event": "session_recovery_attempt",
                    "status": "ok",
                },
            )
            self.assertEqual(response.status_code, 200)
            response = client.post(
                "/api/diagnostics/event",
                json={
                    "route": "/settings",
                    "event": "session_recovery_failed",
                    "status": "error",
                    "detail": "세션 만료",
                },
            )
            self.assertEqual(response.status_code, 200)

            diagnostics = client.get("/api/diagnostics").json()

        self.assertTrue(diagnostics["hydration_failure_summary"]["tracked"])
        self.assertEqual(diagnostics["hydration_failure_summary"]["failure_count"], 1)
        self.assertEqual(diagnostics["session_recovery_summary"]["failure_count"], 1)
        self.assertEqual(diagnostics["session_recovery_summary"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
