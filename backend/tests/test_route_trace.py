import unittest

from app.utils.route_trace import build_route_trace


class RouteTraceTests(unittest.TestCase):
    def test_build_route_trace_infers_partial_served_state(self):
        trace = build_route_trace(
            route_key="radar",
            payload={"partial": True, "fallback_reason": "quick_timeout"},
            request_phase="quick",
            cache_state="miss",
            upstream_source="yfinance",
            elapsed_ms=2500,
            timeout_budget_ms=3000,
        )

        self.assertEqual(trace["route_key"], "radar")
        self.assertEqual(trace["request_phase"], "quick")
        self.assertEqual(trace["cache_state"], "miss")
        self.assertEqual(trace["operation_kind"], "public-read")
        self.assertEqual(trace["served_state"], "partial")
        self.assertEqual(trace["fallback_reason"], "quick_timeout")
        self.assertEqual(trace["failure_class"], "quick_timeout")
        self.assertTrue(trace["recovered"])
        self.assertFalse(trace["cold_start_suspected"])
        self.assertIsInstance(trace["recorded_at"], str)

    def test_build_route_trace_marks_cold_start_on_slow_cache_miss(self):
        trace = build_route_trace(
            route_key="stock_detail",
            payload={"partial": False},
            request_phase="full",
            cache_state="miss",
            upstream_source="yfinance",
            elapsed_ms=5200,
            timeout_budget_ms=4000,
            fallback_reason="full_timeout",
        )

        self.assertTrue(trace["cold_start_suspected"])
        self.assertEqual(trace["served_state"], "fresh")
        self.assertEqual(trace["failure_class"], "full_timeout")
        self.assertTrue(trace["recovered"])

    def test_build_route_trace_marks_stale_served_and_keeps_explicit_fields(self):
        trace = build_route_trace(
            route_key="portfolio",
            request_phase="full",
            cache_state="sqlite_hit",
            elapsed_ms=1800,
            operation_kind="auth-read",
            timeout_budget_ms=12000,
            served_state="stale",
            panel_key="summary",
            dependency_key="supabase",
        )

        self.assertEqual(trace["operation_kind"], "auth-read")
        self.assertEqual(trace["failure_class"], "stale_served")
        self.assertEqual(trace["panel_key"], "summary")
        self.assertEqual(trace["dependency_key"], "supabase")
        self.assertTrue(trace["recovered"])


if __name__ == "__main__":
    unittest.main()
