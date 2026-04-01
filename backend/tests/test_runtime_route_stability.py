import unittest

from app.runtime import get_runtime_state, record_route_observation, reset_runtime_state


class RouteStabilityRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_state()

    def tearDown(self) -> None:
        reset_runtime_state()

    def test_route_stability_summary_tracks_rates_and_percentiles(self):
        record_route_observation(
            "stock_detail",
            {
                "request_phase": "quick",
                "cache_state": "miss",
                "cold_start_suspected": True,
                "upstream_source": "stock_quick_build",
                "elapsed_ms": 1200,
                "timeout_budget_ms": 12000,
                "fallback_reason": "stock_quick_detail",
                "served_state": "partial",
            },
            success=True,
        )
        record_route_observation(
            "stock_detail",
            {
                "request_phase": "full",
                "cache_state": "memory_hit",
                "cold_start_suspected": False,
                "upstream_source": "stock_detail_cache",
                "elapsed_ms": 180,
                "timeout_budget_ms": 0,
                "fallback_reason": None,
                "served_state": "fresh",
            },
            success=True,
        )
        record_route_observation(
            "stock_detail",
            {
                "request_phase": "full",
                "cache_state": "miss",
                "cold_start_suspected": True,
                "upstream_source": "stock_detail_timeout",
                "elapsed_ms": 24000,
                "timeout_budget_ms": 24000,
                "fallback_reason": "stock_detail_timeout",
                "served_state": "degraded",
            },
            success=False,
        )

        state = get_runtime_state()
        self.assertIn("route_stability", state)
        self.assertEqual(len(state["route_stability"]), 1)

        summary = state["route_stability"][0]
        self.assertEqual(summary["route"], "stock_detail")
        self.assertEqual(summary["total_requests"], 3)
        self.assertEqual(summary["success_count"], 2)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["fallback_served_count"], 2)
        self.assertEqual(summary["cold_start_count"], 2)
        self.assertEqual(summary["cold_failure_count"], 1)
        self.assertAlmostEqual(summary["fallback_served_rate"], 2 / 3)
        self.assertAlmostEqual(summary["cold_failure_rate"], 0.5)
        self.assertIsNotNone(summary["first_usable_p50_ms"])
        self.assertIsNotNone(summary["first_usable_p95_ms"])
        self.assertEqual(summary["last_fallback_reason"], "stock_detail_timeout")
        self.assertEqual(summary["last_upstream_source"], "stock_detail_timeout")

    def test_route_stability_tracks_stale_served_state(self):
        record_route_observation(
            "daily_briefing",
            {
                "request_phase": "quick",
                "cache_state": "sqlite_hit",
                "cold_start_suspected": False,
                "upstream_source": "daily_briefing_cache",
                "elapsed_ms": 320,
                "timeout_budget_ms": 0,
                "fallback_reason": "briefing_cached_snapshot",
                "served_state": "stale",
            },
            success=True,
        )

        summary = get_runtime_state()["route_stability"][0]
        self.assertEqual(summary["route"], "daily_briefing")
        self.assertEqual(summary["stale_served_count"], 1)
        self.assertAlmostEqual(summary["stale_served_rate"], 1.0)
        self.assertEqual(summary["cache_counts"]["sqlite_hit"], 1)


if __name__ == "__main__":
    unittest.main()
