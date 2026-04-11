import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.main import app, lifespan, settings as app_settings
from app.runtime import get_runtime_state, reset_runtime_state


class StartupLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_runtime_state()

    async def _wait_for_status(
        self,
        expected_status: str,
        expected_task_statuses: dict[str, str],
        turns: int = 20,
    ):
        last_state = get_runtime_state()
        for _ in range(turns):
            last_state = get_runtime_state()
            tasks = {task["name"]: task for task in last_state["startup_tasks"]}
            if last_state["status"] == expected_status and all(
                tasks.get(name, {}).get("status") == status
                for name, status in expected_task_statuses.items()
            ):
                return last_state
            await asyncio.sleep(0)
        return last_state

    async def test_startup_runs_background_tasks_without_blocking_app_boot(self):
        fusion_gate = asyncio.Event()
        accuracy_gate = asyncio.Event()
        research_gate = asyncio.Event()
        radar_gate = asyncio.Event()

        async def wait_for_fusion(*args, **kwargs):
            await fusion_gate.wait()

        async def wait_for_accuracy(*args, **kwargs):
            await accuracy_gate.wait()

        async def wait_for_research(*args, **kwargs):
            await research_gate.wait()

        async def wait_for_radar(*args, **kwargs):
            await radar_gate.wait()

        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(side_effect=wait_for_fusion),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=wait_for_accuracy),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(side_effect=wait_for_research),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=wait_for_radar),
            ),
        ):
            async with lifespan(app):
                state = get_runtime_state()
                self.assertEqual(state["status"], "starting")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["database_initialize"]["status"], "ok")
                self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "running")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "running")
                self.assertEqual(tasks["research_archive_sync"]["status"], "running")
                self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "queued")

                fusion_gate.set()
                accuracy_gate.set()
                research_gate.set()
                radar_gate.set()
                state = await self._wait_for_status(
                    "ok",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                    },
                )
                self.assertEqual(state["status"], "ok")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "ok")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "ok")
                self.assertEqual(tasks["research_archive_sync"]["status"], "ok")
                self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "ok")

    async def test_startup_continues_when_learned_fusion_refresh_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(side_effect=RuntimeError("fusion refresh failed")),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "degraded",
                    {
                        "learned_fusion_profile_refresh": "warning",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                    },
                )

        self.assertEqual(state["status"], "degraded")
        tasks = {task["name"]: task for task in state["startup_tasks"]}
        self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "warning")

    async def test_startup_continues_when_accuracy_refresh_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=RuntimeError("refresh failed")),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "degraded",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "warning",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                    },
                )
                self.assertEqual(state["status"], "degraded")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["database_initialize"]["status"], "ok")
                self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "ok")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "warning")
                self.assertEqual(tasks["research_archive_sync"]["status"], "ok")
                self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "ok")

    async def test_startup_continues_when_market_opportunity_prewarm_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=RuntimeError("radar prewarm failed")),
            ),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "degraded",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "warning",
                    },
                )
                self.assertEqual(state["status"], "degraded")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["database_initialize"]["status"], "ok")
                self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "warning")

    async def test_startup_timeout_marks_task_ok_without_degraded_health(self):
        async def slow_accuracy(*args, **kwargs):
            await asyncio.sleep(0.03)

        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=slow_accuracy),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ),
            patch.object(app_settings, "startup_prediction_accuracy_refresh_timeout", 0.001),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "ok",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                    },
                )

        self.assertEqual(state["status"], "ok")
        tasks = {task["name"]: task for task in state["startup_tasks"]}
        self.assertIn(
            "Startup window ended before prediction accuracy refresh finished",
            tasks["prediction_accuracy_refresh"]["detail"],
        )

    async def test_startup_queues_tasks_when_concurrency_is_one(self):
        fusion_gate = asyncio.Event()
        accuracy_gate = asyncio.Event()
        research_gate = asyncio.Event()
        radar_gate = asyncio.Event()

        async def wait_for_fusion(*args, **kwargs):
            await fusion_gate.wait()

        async def wait_for_accuracy(*args, **kwargs):
            await accuracy_gate.wait()

        async def wait_for_research(*args, **kwargs):
            await research_gate.wait()

        async def wait_for_radar(*args, **kwargs):
            await radar_gate.wait()

        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(side_effect=wait_for_fusion),
            ),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=wait_for_accuracy),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(side_effect=wait_for_research),
            ),
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=wait_for_radar),
            ),
            patch.object(app_settings, "startup_background_task_concurrency", 1),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "starting",
                    {
                        "learned_fusion_profile_refresh": "running",
                        "prediction_accuracy_refresh": "queued",
                        "research_archive_sync": "queued",
                        "market_opportunity_prewarm": "queued",
                    },
                )
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "running")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "queued")
                self.assertEqual(tasks["research_archive_sync"]["status"], "queued")
                self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "queued")

                fusion_gate.set()
                state = await self._wait_for_status(
                    "starting",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "running",
                        "research_archive_sync": "queued",
                        "market_opportunity_prewarm": "queued",
                    },
                )

                accuracy_gate.set()
                state = await self._wait_for_status(
                    "starting",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "running",
                        "market_opportunity_prewarm": "queued",
                    },
                )

                research_gate.set()
                state = await self._wait_for_status(
                    "starting",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "running",
                    },
                )

                radar_gate.set()
                state = await self._wait_for_status(
                    "ok",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                    },
                )
                self.assertEqual(state["status"], "ok")

    async def test_startup_marks_disabled_tasks_as_skipped(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ) as fusion_refresh,
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(return_value=None),
            ) as accuracy_refresh,
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ) as research_sync,
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ) as radar_prewarm,
            patch.object(app_settings, "startup_learned_fusion_refresh", False),
            patch.object(app_settings, "startup_prediction_accuracy_refresh", False),
            patch.object(app_settings, "startup_research_archive_sync", False),
            patch.object(app_settings, "startup_market_opportunity_prewarm", False),
        ):
            async with lifespan(app):
                state = get_runtime_state()

        self.assertEqual(state["status"], "ok")
        tasks = {task["name"]: task for task in state["startup_tasks"]}
        self.assertEqual(tasks["learned_fusion_profile_refresh"]["status"], "ok")
        self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "ok")
        self.assertEqual(tasks["research_archive_sync"]["status"], "ok")
        self.assertEqual(tasks["market_opportunity_prewarm"]["status"], "ok")
        self.assertIn("skipped by configuration", tasks["learned_fusion_profile_refresh"]["detail"])
        self.assertIn("skipped by configuration", tasks["prediction_accuracy_refresh"]["detail"])
        self.assertIn("skipped by configuration", tasks["research_archive_sync"]["detail"])
        self.assertIn("skipped by configuration", tasks["market_opportunity_prewarm"]["detail"])
        fusion_refresh.assert_not_called()
        accuracy_refresh.assert_not_called()
        research_sync.assert_not_called()
        radar_prewarm.assert_not_called()

    async def test_render_memory_safe_mode_skips_heavy_startup_jobs(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ) as fusion_refresh,
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(return_value=None),
            ) as accuracy_refresh,
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ) as research_sync,
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ) as radar_prewarm,
            patch(
                "app.main.country.prewarm_market_indicators_cache",
                new=AsyncMock(return_value=None),
            ) as indicators_prewarm,
            patch(
                "app.main.briefing.prewarm_daily_briefing_cache",
                new=AsyncMock(return_value=None),
            ) as briefing_prewarm,
            patch(
                "app.main.screener.prewarm_public_screener_cache_seed",
                new=AsyncMock(return_value=None),
            ) as screener_prewarm,
            patch.object(app_settings, "render_environment", True),
            patch.object(app_settings, "render_service_name", "stock-predict-api"),
            patch.object(app_settings, "startup_allow_heavy_render_jobs", False),
            patch.object(app_settings, "startup_learned_fusion_refresh", True),
            patch.object(app_settings, "startup_prediction_accuracy_refresh", True),
            patch.object(app_settings, "startup_prediction_accuracy_refresh_on_render", True),
            patch.object(app_settings, "startup_research_archive_sync", True),
            patch.object(app_settings, "startup_market_opportunity_prewarm", True),
            patch.object(app_settings, "startup_market_opportunity_prewarm_timeout", 180),
            patch.object(app_settings, "startup_background_task_concurrency", 3),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "ok",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                        "public_dashboard_prewarm": "ok",
                    },
                )

        tasks = {task["name"]: task for task in state["startup_tasks"]}
        self.assertIn(
            "Render 메모리 세이프 startup 프로필",
            tasks["learned_fusion_profile_refresh"]["detail"],
        )
        self.assertIn(
            "Render 메모리 세이프 startup 프로필",
            tasks["prediction_accuracy_refresh"]["detail"],
        )
        self.assertIn(
            "Render 메모리 세이프 startup 프로필",
            tasks["research_archive_sync"]["detail"],
        )
        self.assertIn(
            "Render 메모리 세이프 startup 프로필",
            tasks["market_opportunity_prewarm"]["detail"],
        )
        fusion_refresh.assert_not_called()
        accuracy_refresh.assert_not_called()
        research_sync.assert_not_called()
        radar_prewarm.assert_not_called()
        indicators_prewarm.assert_awaited_once()
        briefing_prewarm.assert_awaited_once()
        screener_prewarm.assert_awaited_once()

    async def test_render_memory_safe_mode_continues_when_public_dashboard_prewarm_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.learned_fusion_profile_service.refresh_profiles",
                new=AsyncMock(return_value={}),
            ) as fusion_refresh,
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(return_value=None),
            ) as accuracy_refresh,
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ) as research_sync,
            patch(
                "app.main.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"country_code": "KR", "opportunities": []}),
            ) as radar_prewarm,
            patch(
                "app.main.country.prewarm_market_indicators_cache",
                new=AsyncMock(side_effect=RuntimeError("indicator prewarm failed")),
            ) as indicators_prewarm,
            patch(
                "app.main.briefing.prewarm_daily_briefing_cache",
                new=AsyncMock(return_value=None),
            ) as briefing_prewarm,
            patch(
                "app.main.screener.prewarm_public_screener_cache_seed",
                new=AsyncMock(return_value=None),
            ) as screener_prewarm,
            patch.object(app_settings, "render_environment", True),
            patch.object(app_settings, "render_service_name", "stock-predict-api"),
            patch.object(app_settings, "startup_allow_heavy_render_jobs", False),
            patch.object(app_settings, "startup_learned_fusion_refresh", True),
            patch.object(app_settings, "startup_prediction_accuracy_refresh", True),
            patch.object(app_settings, "startup_prediction_accuracy_refresh_on_render", True),
            patch.object(app_settings, "startup_research_archive_sync", True),
            patch.object(app_settings, "startup_market_opportunity_prewarm", True),
            patch.object(app_settings, "startup_market_opportunity_prewarm_timeout", 180),
            patch.object(app_settings, "startup_background_task_concurrency", 3),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "degraded",
                    {
                        "learned_fusion_profile_refresh": "ok",
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                        "market_opportunity_prewarm": "ok",
                        "public_dashboard_prewarm": "warning",
                    },
                )

        tasks = {task["name"]: task for task in state["startup_tasks"]}
        self.assertEqual(tasks["public_dashboard_prewarm"]["status"], "warning")
        self.assertIn("indicator prewarm failed", tasks["public_dashboard_prewarm"]["detail"])
        fusion_refresh.assert_not_called()
        accuracy_refresh.assert_not_called()
        research_sync.assert_not_called()
        radar_prewarm.assert_not_called()
        indicators_prewarm.assert_awaited_once()
        briefing_prewarm.assert_not_called()
        screener_prewarm.assert_not_called()

    async def test_startup_raises_when_database_init_fails(self):
        with patch("app.main.db.initialize", new=AsyncMock(side_effect=RuntimeError("db failed"))):
            with self.assertRaises(RuntimeError):
                async with lifespan(app):
                    pass


if __name__ == "__main__":
    unittest.main()
