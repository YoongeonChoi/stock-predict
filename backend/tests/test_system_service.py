import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import system_service


class SystemServiceTests(unittest.IsolatedAsyncioTestCase):
    def _settings_stub(self) -> SimpleNamespace:
        return SimpleNamespace(
            openai_api_key="",
            fmp_api_key="",
            ecos_api_key="",
            opendart_api_key="",
            kosis_api_key="",
            kosis_cpi_stats_id="",
            kosis_employment_stats_id="",
            kosis_industrial_production_stats_id="",
            naver_client_id="",
            naver_client_secret="",
            diagnostics_probe_timeout_seconds=1,
            runtime_memory_budget_mb=500,
            startup_memory_safe_mode=True,
        )

    async def test_get_diagnostics_surfaces_failure_class_summary(self):
        route_summary = {
            "routes": [],
            "first_usable_metrics": {
                "tracked_routes": 1,
                "total_requests": 2,
                "p50_elapsed_ms": 120.0,
                "p95_elapsed_ms": 210.0,
                "fallback_served_rate": 0.5,
                "stale_served_rate": 0.25,
                "first_request_cold_failure_rate": 0.5,
                "blank_screen_rate": 0.0,
                "error_only_screen_rate": 0.0,
            },
            "hydration_failure_summary": {
                "tracked": True,
                "total": 2,
                "failure_count": 1,
                "failure_rate": 0.5,
                "by_route": [{"route": "/", "total": 2, "failure_count": 1, "failure_rate": 0.5}],
            },
            "session_recovery_summary": {
                "tracked": True,
                "total": 1,
                "failure_count": 0,
                "failure_rate": 0.0,
                "by_route": [],
            },
            "failure_class_summary": {
                "tracked": True,
                "total": 3,
                "by_class": {"quick_timeout": 2, "panel_fetch_failed": 1},
                "recovered_count": 2,
                "recovered_rate": 0.6667,
            },
        }

        with (
            patch("app.services.system_service.get_settings", return_value=self._settings_stub()),
            patch("app.services.system_service.get_runtime_state", return_value={"status": "ok", "started_at": "2026-04-03T00:00:00Z", "startup_tasks": []}),
            patch("app.services.system_service.archive_service.get_accuracy", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.research_archive_service.get_public_research_status", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.confidence_calibration_service.get_profile_summary", return_value=[]),
            patch("app.services.system_service._build_learned_fusion_status", return_value=None),
            patch("app.services.system_service.route_stability_service.get_route_stability_summary", return_value=route_summary),
        ):
            diagnostics = await system_service.get_diagnostics()

        self.assertEqual(diagnostics["failure_class_summary"], route_summary["failure_class_summary"])
        self.assertEqual(diagnostics["first_usable_metrics"], route_summary["first_usable_metrics"])

    async def test_get_diagnostics_uses_failure_class_fallback_when_summary_errors(self):
        with (
            patch("app.services.system_service.get_settings", return_value=self._settings_stub()),
            patch("app.services.system_service.get_runtime_state", return_value={"status": "ok", "started_at": "2026-04-03T00:00:00Z", "startup_tasks": []}),
            patch("app.services.system_service.archive_service.get_accuracy", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.research_archive_service.get_public_research_status", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.confidence_calibration_service.get_profile_summary", return_value=[]),
            patch("app.services.system_service._build_learned_fusion_status", return_value=None),
            patch("app.services.system_service.route_stability_service.get_route_stability_summary", side_effect=RuntimeError("boom")),
        ):
            diagnostics = await system_service.get_diagnostics()

        self.assertEqual(
            diagnostics["failure_class_summary"],
            {
                "tracked": False,
                "total": 0,
                "by_class": {},
                "recovered_count": 0,
                "recovered_rate": 0.0,
            },
        )
        self.assertEqual(diagnostics["route_stability_summary"], [])

    async def test_get_diagnostics_includes_memory_diagnostics(self):
        route_summary = {
            "routes": [],
            "first_usable_metrics": {
                "tracked_routes": 0,
                "total_requests": 0,
                "p50_elapsed_ms": 0.0,
                "p95_elapsed_ms": 0.0,
                "fallback_served_rate": 0.0,
                "stale_served_rate": 0.0,
                "first_request_cold_failure_rate": 0.0,
                "blank_screen_rate": 0.0,
                "error_only_screen_rate": 0.0,
            },
            "hydration_failure_summary": {"tracked": False, "total": 0, "failure_count": 0, "failure_rate": 0.0, "by_route": []},
            "session_recovery_summary": {"tracked": False, "total": 0, "failure_count": 0, "failure_rate": 0.0, "by_route": []},
            "failure_class_summary": {"tracked": False, "total": 0, "by_class": {}, "recovered_count": 0, "recovered_rate": 0.0},
        }
        memory_snapshot = {
            "source": "proc_status",
            "rss_bytes": 123,
            "rss_mb": 0.12,
            "peak_rss_bytes": 456,
            "peak_rss_mb": 0.45,
            "cgroup_current_bytes": 789,
            "cgroup_current_mb": 0.75,
            "cgroup_limit_bytes": 104857600,
            "cgroup_limit_mb": 100.0,
            "configured_budget_mb": 500,
            "resolved_budget_mb": 100.0,
            "pressure_ratio": 0.0075,
            "pressure_state": "ok",
            "memory_cache": {"entry_count": 2, "estimated_bytes": 2048},
            "render_memory_safe_mode": True,
        }

        with (
            patch("app.services.system_service.get_settings", return_value=self._settings_stub()),
            patch("app.services.system_service.get_runtime_state", return_value={"status": "ok", "started_at": "2026-04-03T00:00:00Z", "startup_tasks": []}),
            patch("app.services.system_service.archive_service.get_accuracy", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.research_archive_service.get_public_research_status", new=AsyncMock(return_value=None)),
            patch("app.services.system_service.confidence_calibration_service.get_profile_summary", return_value=[]),
            patch("app.services.system_service._build_learned_fusion_status", return_value=None),
            patch("app.services.system_service.route_stability_service.get_route_stability_summary", return_value=route_summary),
            patch("app.services.system_service._get_process_memory_snapshot", return_value=memory_snapshot),
        ):
            diagnostics = await system_service.get_diagnostics()

        self.assertEqual(diagnostics["memory_diagnostics"], memory_snapshot)
        self.assertTrue(diagnostics["render_memory_safe_mode"])

    async def test_get_diagnostics_runs_best_effort_probes_concurrently(self):
        route_summary = {
            "routes": [],
            "first_usable_metrics": {
                "tracked_routes": 0,
                "total_requests": 0,
                "p50_elapsed_ms": 0.0,
                "p95_elapsed_ms": 0.0,
                "fallback_served_rate": 0.0,
                "stale_served_rate": 0.0,
                "first_request_cold_failure_rate": 0.0,
                "blank_screen_rate": 0.0,
                "error_only_screen_rate": 0.0,
            },
            "hydration_failure_summary": {"tracked": False, "total": 0, "failure_count": 0, "failure_rate": 0.0, "by_route": []},
            "session_recovery_summary": {"tracked": False, "total": 0, "failure_count": 0, "failure_rate": 0.0, "by_route": []},
            "failure_class_summary": {"tracked": False, "total": 0, "by_class": {}, "recovered_count": 0, "recovered_rate": 0.0},
        }
        started_accuracy = asyncio.Event()
        started_research = asyncio.Event()
        release = asyncio.Event()

        async def _slow_accuracy(refresh: bool = False):
            started_accuracy.set()
            await release.wait()
            return None

        async def _slow_research(refresh_if_missing: bool = False):
            started_research.set()
            await release.wait()
            return None

        with (
            patch("app.services.system_service.get_settings", return_value=self._settings_stub()),
            patch("app.services.system_service.get_runtime_state", return_value={"status": "ok", "started_at": "2026-04-03T00:00:00Z", "startup_tasks": []}),
            patch("app.services.system_service.archive_service.get_accuracy", new=AsyncMock(side_effect=_slow_accuracy)),
            patch("app.services.system_service.research_archive_service.get_public_research_status", new=AsyncMock(side_effect=_slow_research)),
            patch("app.services.system_service.confidence_calibration_service.get_profile_summary", return_value=[]),
            patch("app.services.system_service._build_learned_fusion_status", return_value=None),
            patch("app.services.system_service.route_stability_service.get_route_stability_summary", return_value=route_summary),
            patch("app.services.system_service._get_process_memory_snapshot", return_value={"source": "unavailable"}),
        ):
            diagnostics_task = asyncio.create_task(system_service.get_diagnostics())
            await asyncio.wait_for(started_accuracy.wait(), timeout=0.2)
            await asyncio.wait_for(started_research.wait(), timeout=0.2)
            release.set()
            diagnostics = await asyncio.wait_for(diagnostics_task, timeout=0.2)

        self.assertIn("memory_diagnostics", diagnostics)


if __name__ == "__main__":
    unittest.main()
