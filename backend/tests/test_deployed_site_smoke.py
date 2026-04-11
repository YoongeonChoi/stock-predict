from __future__ import annotations

import importlib.util
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_deployed_smoke_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "scripts" / "deployed_site_smoke.py"
    spec = importlib.util.spec_from_file_location("deployed_site_smoke_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


deployed_smoke = _load_deployed_smoke_module()


class DeployedSiteSmokeTests(unittest.TestCase):
    def test_parse_args_supports_fast_failure_controls(self):
        args = deployed_smoke.parse_args(
            [
                "--api-timeout",
                "12",
                "--frontend-timeout",
                "18",
                "--attempts",
                "2",
                "--retry-delay",
                "1.25",
                "--max-total-seconds",
                "90",
                "--fail-fast",
            ]
        )

        self.assertEqual(args.api_timeout, 12)
        self.assertEqual(args.frontend_timeout, 18)
        self.assertEqual(args.attempts, 2)
        self.assertEqual(args.retry_delay, 1.25)
        self.assertEqual(args.max_total_seconds, 90)
        self.assertTrue(args.fail_fast)

    def test_clamp_timeout_caps_long_contract_timeout(self):
        self.assertEqual(deployed_smoke.clamp_timeout(45, 15), 15)
        self.assertEqual(deployed_smoke.clamp_timeout(8, 15), 8)

    def test_fetch_with_retry_stops_when_budget_is_already_exhausted(self):
        with patch.object(deployed_smoke, "fetch", side_effect=AssertionError("fetch should not run")):
            with self.assertRaisesRegex(RuntimeError, "budget was exhausted"):
                deployed_smoke.fetch_with_retry(
                    "https://api.example.com/health",
                    attempts=1,
                    timeout=10,
                    deadline=time.monotonic() - 1,
                )

    def test_summarize_api_payload_includes_partial_and_memory_diagnostics(self):
        check = deployed_smoke.ApiSmokeCheck(name="diagnostics", method="GET", path="/api/diagnostics")
        payload = {
            "partial": True,
            "fallback_reason": "stock_quick_detail",
            "memory_diagnostics": {
                "rss_mb": 207.61,
                "cgroup_current_mb": 232.69,
                "pressure_ratio": 0.4545,
                "pressure_state": "ok",
            },
        }

        summary = deployed_smoke.summarize_api_payload(check, payload)

        self.assertIn("partial=True", summary)
        self.assertIn("fallback=stock_quick_detail", summary)
        self.assertIn("rss=207.61MB", summary)
        self.assertIn("cgroup=232.69MB", summary)
        self.assertIn("pressure=0.4545", summary)
        self.assertIn("state=ok", summary)

    def test_main_success_output_includes_elapsed_and_payload_summary(self):
        check = deployed_smoke.ApiSmokeCheck(name="stock-detail", method="GET", path="/api/stock/003670/detail")
        body = '{"partial": true, "fallback_reason": "stock_quick_detail"}'

        with (
            patch.object(deployed_smoke, "build_api_checks", return_value=[(check, "https://api.example.com/api/stock/003670/detail")]),
            patch.object(deployed_smoke, "build_frontend_checks", return_value=[]),
            patch.object(deployed_smoke, "fetch_with_retry", return_value=(200, body, {})),
            patch.object(deployed_smoke.time, "monotonic", side_effect=[100.0, 100.25]),
            patch("builtins.print") as print_mock,
        ):
            exit_code = deployed_smoke.main([])

        self.assertEqual(exit_code, 0)
        printed = " ".join(" ".join(str(arg) for arg in call.args) for call in print_mock.call_args_list)
        self.assertIn("stock-detail", printed)
        self.assertIn("in 0.25s", printed)
        self.assertIn("partial=True", printed)
        self.assertIn("fallback=stock_quick_detail", printed)

    def test_main_fail_fast_stops_after_first_api_failure(self):
        first = deployed_smoke.ApiSmokeCheck(name="health", method="GET", path="/api/health")
        second = deployed_smoke.ApiSmokeCheck(name="countries", method="GET", path="/api/countries")

        with (
            patch.object(
                deployed_smoke,
                "build_api_checks",
                return_value=[
                    (first, "https://api.example.com/api/health"),
                    (second, "https://api.example.com/api/countries"),
                ],
            ),
            patch.object(deployed_smoke, "build_frontend_checks", return_value=[]) as frontend_checks,
            patch.object(deployed_smoke, "fetch_with_retry", side_effect=RuntimeError("timed out")) as fetch_with_retry,
            patch("builtins.print"),
        ):
            exit_code = deployed_smoke.main(["--fail-fast", "--attempts", "1"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(fetch_with_retry.call_count, 1)
        frontend_checks.assert_not_called()


if __name__ == "__main__":
    unittest.main()
