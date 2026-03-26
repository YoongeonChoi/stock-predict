import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.main import app, lifespan
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
        accuracy_gate = asyncio.Event()
        research_gate = asyncio.Event()

        async def wait_for_accuracy(*args, **kwargs):
            await accuracy_gate.wait()

        async def wait_for_research(*args, **kwargs):
            await research_gate.wait()

        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=wait_for_accuracy),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(side_effect=wait_for_research),
            ),
        ):
            async with lifespan(app):
                state = get_runtime_state()
                self.assertEqual(state["status"], "starting")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["database_initialize"]["status"], "ok")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "running")
                self.assertEqual(tasks["research_archive_sync"]["status"], "running")

                accuracy_gate.set()
                research_gate.set()
                state = await self._wait_for_status(
                    "ok",
                    {
                        "prediction_accuracy_refresh": "ok",
                        "research_archive_sync": "ok",
                    },
                )
                self.assertEqual(state["status"], "ok")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "ok")
                self.assertEqual(tasks["research_archive_sync"]["status"], "ok")

    async def test_startup_continues_when_accuracy_refresh_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch(
                "app.main.archive_service.refresh_prediction_accuracy",
                new=AsyncMock(side_effect=RuntimeError("refresh failed")),
            ),
            patch(
                "app.main.research_archive_service.sync_public_research_reports",
                new=AsyncMock(return_value={"processed_total": 0}),
            ),
        ):
            async with lifespan(app):
                state = await self._wait_for_status(
                    "degraded",
                    {
                        "prediction_accuracy_refresh": "warning",
                        "research_archive_sync": "ok",
                    },
                )
                self.assertEqual(state["status"], "degraded")
                tasks = {task["name"]: task for task in state["startup_tasks"]}
                self.assertEqual(tasks["database_initialize"]["status"], "ok")
                self.assertEqual(tasks["prediction_accuracy_refresh"]["status"], "warning")
                self.assertEqual(tasks["research_archive_sync"]["status"], "ok")

    async def test_startup_raises_when_database_init_fails(self):
        with patch("app.main.db.initialize", new=AsyncMock(side_effect=RuntimeError("db failed"))):
            with self.assertRaises(RuntimeError):
                async with lifespan(app):
                    pass


if __name__ == "__main__":
    unittest.main()
