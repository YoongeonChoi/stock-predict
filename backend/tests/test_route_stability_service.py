from __future__ import annotations

import unittest

from app.services import route_stability_service
from app.utils.route_trace import build_route_trace


class RouteStabilityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        route_stability_service.reset_route_stability_state()

    def test_route_stability_summary_tracks_rates_percentiles_and_failure_classes(self) -> None:
        route_stability_service.record_route_trace(
            "stock_detail",
            build_route_trace(
                route_key="stock_detail",
                request_phase="quick",
                cache_state="sqlite_hit",
                elapsed_ms=3200,
                operation_kind="public-read",
                timeout_budget_ms=12000,
                fallback_reason="quick_timeout",
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
                operation_kind="public-read",
                timeout_budget_ms=12000,
                served_state="fresh",
                fallback_reason="full_timeout",
            ),
        )
        route_stability_service.record_route_trace(
            "stock_detail",
            build_route_trace(
                route_key="stock_detail",
                request_phase="full",
                cache_state="sqlite_hit",
                elapsed_ms=2100,
                operation_kind="public-read",
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
        self.assertEqual(stock_row["operation_kind_mix"]["public-read"], 3)
        self.assertEqual(stock_row["cache_state_mix"]["sqlite_hit"], 2)
        self.assertGreater(stock_row["fallback_served_rate"], 0)
        self.assertGreater(stock_row["stale_rate"], 0)
        self.assertEqual(stock_row["failure_class_mix"]["stale_served"], 1)
        self.assertEqual(stock_row["failure_class_mix"]["quick_timeout"], 1)
        self.assertEqual(stock_row["failure_class_mix"]["full_timeout"], 1)
        self.assertEqual(summary["failure_class_summary"]["by_class"]["stale_served"], 1)
        self.assertEqual(summary["failure_class_summary"]["total"], 3)

    def test_frontend_events_update_hydration_session_and_failure_class_summary(self) -> None:
        route_stability_service.record_frontend_event(
            route="/portfolio",
            event="panel_degraded",
            status="warning",
            panel="conditional_recommendation",
            detail="조건 추천 응답이 지연되고 있습니다.",
        )
        route_stability_service.record_frontend_event(
            route="/settings",
            event="session_recovery_attempt",
            status="ok",
        )
        route_stability_service.record_frontend_event(
            route="/settings",
            event="session_recovery_failed",
            status="error",
            detail="세션이 만료되었습니다.",
        )

        summary = route_stability_service.get_route_stability_summary()

        self.assertTrue(summary["hydration_failure_summary"]["tracked"])
        self.assertEqual(summary["hydration_failure_summary"]["failure_count"], 1)
        self.assertEqual(summary["session_recovery_summary"]["failure_count"], 1)
        self.assertEqual(summary["session_recovery_summary"]["total"], 1)
        self.assertEqual(summary["failure_class_summary"]["by_class"]["panel_fetch_failed"], 1)
        self.assertEqual(summary["failure_class_summary"]["by_class"]["session_recovery_failed"], 1)


if __name__ == "__main__":
    unittest.main()
