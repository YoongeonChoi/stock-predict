import unittest
from unittest.mock import AsyncMock, patch

from app.main import app, lifespan
from app.runtime import get_runtime_state, reset_runtime_state


class StartupLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_runtime_state()

    async def test_startup_continues_when_accuracy_refresh_fails(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch("app.main.archive_service.refresh_prediction_accuracy", new=AsyncMock(side_effect=RuntimeError("refresh failed"))),
            patch("app.main.research_archive_service.sync_public_research_reports", new=AsyncMock(return_value={"processed_total": 0})),
        ):
            async with lifespan(app):
                state = get_runtime_state()
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
