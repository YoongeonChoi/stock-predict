import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.utils import memory_hygiene


class MemoryHygieneTests(unittest.TestCase):
    def setUp(self):
        memory_hygiene.reset_memory_trim_state()

    def _settings(self, *, safe_mode: bool) -> SimpleNamespace:
        return SimpleNamespace(
            startup_memory_safe_mode=safe_mode,
            runtime_memory_budget_mb=500,
        )

    def test_trim_skips_when_not_render_safe(self):
        with patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=False)):
            result = memory_hygiene.maybe_trim_process_memory("countries")

        self.assertFalse(result["attempted"])
        self.assertEqual(result["skipped"], "not_render_safe")

    def test_trim_runs_gc_and_malloc_trim_when_pressure_is_high(self):
        before = {
            "current_bytes": 420 * 1024 * 1024,
            "rss_bytes": 420 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 420 * 1024 * 1024,
            "pressure_ratio": 420 / 512,
        }
        after = {
            "current_bytes": 330 * 1024 * 1024,
            "rss_bytes": 330 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 330 * 1024 * 1024,
            "pressure_ratio": 330 / 512,
        }
        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch("app.utils.memory_hygiene._get_pressure_snapshot", side_effect=[before, after]),
            patch("app.utils.memory_hygiene.gc.collect", return_value=17) as collect,
            patch("app.utils.memory_hygiene._try_malloc_trim", return_value=True) as malloc_trim,
        ):
            result = memory_hygiene.maybe_trim_process_memory("country_report")

        self.assertTrue(result["attempted"])
        self.assertTrue(result["trimmed"])
        self.assertEqual(result["before_mb"], 420.0)
        self.assertEqual(result["after_mb"], 330.0)
        collect.assert_called_once()
        malloc_trim.assert_called_once()
        stats = memory_hygiene.get_memory_trim_stats()
        self.assertEqual(stats["attempts"], 1)
        self.assertEqual(stats["successes"], 1)
        self.assertEqual(stats["last_reason"], "country_report")

    def test_trim_runs_at_warning_pressure_before_crossing_critical(self):
        before = {
            "current_bytes": 330 * 1024 * 1024,
            "rss_bytes": 330 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 330 * 1024 * 1024,
            "pressure_ratio": 330 / 512,
        }
        after = {
            "current_bytes": 300 * 1024 * 1024,
            "rss_bytes": 300 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 300 * 1024 * 1024,
            "pressure_ratio": 300 / 512,
        }
        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch("app.utils.memory_hygiene._get_pressure_snapshot", side_effect=[before, after]),
            patch("app.utils.memory_hygiene.gc.collect", return_value=11) as collect,
            patch("app.utils.memory_hygiene._try_malloc_trim", return_value=True) as malloc_trim,
        ):
            result = memory_hygiene.maybe_trim_process_memory("warning_band")

        self.assertTrue(result["attempted"])
        self.assertEqual(result["before_mb"], 330.0)
        self.assertEqual(result["after_mb"], 300.0)
        collect.assert_called_once()
        malloc_trim.assert_called_once()

    def test_trim_respects_cooldown(self):
        snapshot = {
            "current_bytes": 390 * 1024 * 1024,
            "rss_bytes": 390 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 390 * 1024 * 1024,
            "pressure_ratio": 390 / 512,
        }
        reduced = {
            "current_bytes": 360 * 1024 * 1024,
            "rss_bytes": 360 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 360 * 1024 * 1024,
            "pressure_ratio": 360 / 512,
        }
        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch("app.utils.memory_hygiene._get_pressure_snapshot", side_effect=[snapshot, reduced, snapshot]),
            patch("app.utils.memory_hygiene.gc.collect", return_value=3),
            patch("app.utils.memory_hygiene._try_malloc_trim", return_value=True),
        ):
            first = memory_hygiene.maybe_trim_process_memory("countries")
            second = memory_hygiene.maybe_trim_process_memory("countries")

        self.assertTrue(first["attempted"])
        self.assertFalse(second["attempted"])
        self.assertEqual(second["skipped"], "cooldown")
        stats = memory_hygiene.get_memory_trim_stats()
        self.assertEqual(stats["attempts"], 1)

    def test_trim_bypasses_cooldown_when_pressure_is_critical(self):
        critical_before = {
            "current_bytes": 490 * 1024 * 1024,
            "rss_bytes": 490 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 490 * 1024 * 1024,
            "pressure_ratio": 490 / 512,
        }
        critical_after = {
            "current_bytes": 470 * 1024 * 1024,
            "rss_bytes": 470 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 470 * 1024 * 1024,
            "pressure_ratio": 470 / 512,
        }
        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch(
                "app.utils.memory_hygiene._get_pressure_snapshot",
                side_effect=[critical_before, critical_after, critical_before, critical_after],
            ),
            patch("app.utils.memory_hygiene.gc.collect", return_value=5),
            patch("app.utils.memory_hygiene._try_malloc_trim", return_value=True),
        ):
            first = memory_hygiene.maybe_trim_process_memory("critical-a")
            second = memory_hygiene.maybe_trim_process_memory("critical-b")

        self.assertTrue(first["attempted"])
        self.assertTrue(second["attempted"])
        self.assertTrue(second["cooldown_bypassed"])
        stats = memory_hygiene.get_memory_trim_stats()
        self.assertEqual(stats["attempts"], 2)
        self.assertTrue(stats["last_cooldown_bypassed"])

    def test_trim_bypasses_cooldown_when_pressure_is_elevated_warning(self):
        warning_before = {
            "current_bytes": 430 * 1024 * 1024,
            "rss_bytes": 430 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 430 * 1024 * 1024,
            "pressure_ratio": 430 / 512,
        }
        warning_after = {
            "current_bytes": 418 * 1024 * 1024,
            "rss_bytes": 418 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 418 * 1024 * 1024,
            "pressure_ratio": 418 / 512,
        }
        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch(
                "app.utils.memory_hygiene._get_pressure_snapshot",
                side_effect=[warning_before, warning_after, warning_before, warning_after],
            ),
            patch("app.utils.memory_hygiene.gc.collect", return_value=7),
            patch("app.utils.memory_hygiene._try_malloc_trim", return_value=True),
        ):
            first = memory_hygiene.maybe_trim_process_memory("warning-a")
            second = memory_hygiene.maybe_trim_process_memory("warning-b")

        self.assertTrue(first["attempted"])
        self.assertTrue(second["attempted"])
        self.assertTrue(second["cooldown_bypassed"])
        stats = memory_hygiene.get_memory_trim_stats()
        self.assertEqual(stats["attempts"], 2)
        self.assertTrue(stats["last_cooldown_bypassed"])

    def test_pressure_snapshot_uses_budget_bytes_from_runtime_snapshot(self):
        raw_snapshot = {
            "current_bytes": 440 * 1024 * 1024,
            "rss_bytes": 470 * 1024 * 1024,
            "budget_bytes": 512 * 1024 * 1024,
            "observed_bytes": 440 * 1024 * 1024,
            "pressure_ratio": 440 / 512,
        }

        with (
            patch("app.utils.memory_hygiene.get_settings", return_value=self._settings(safe_mode=True)),
            patch("app.utils.memory_hygiene._get_pressure_snapshot", return_value=raw_snapshot),
        ):
            snapshot = memory_hygiene.get_memory_pressure_snapshot()

        self.assertEqual(snapshot["observed_mb"], 440.0)
        self.assertEqual(snapshot["resolved_budget_mb"], 512.0)
        self.assertAlmostEqual(snapshot["pressure_ratio"], round(440 / 512, 4))
        self.assertEqual(snapshot["pressure_state"], "warning")


if __name__ == "__main__":
    unittest.main()
