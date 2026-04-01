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
        self.assertEqual(trace["served_state"], "partial")
        self.assertEqual(trace["fallback_reason"], "quick_timeout")
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
        )

        self.assertTrue(trace["cold_start_suspected"])
        self.assertEqual(trace["served_state"], "fresh")


if __name__ == "__main__":
    unittest.main()
