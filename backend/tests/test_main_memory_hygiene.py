import unittest
import asyncio
import threading
import time
from unittest.mock import PropertyMock, patch

import app.main as main_module
from app.main import settings as app_settings
from tests.client_helpers import patched_client


class MainMemoryHygieneMiddlewareTests(unittest.TestCase):
    def test_health_check_does_not_trigger_pre_request_trim(self):
        with (
            patch("app.main._maybe_schedule_public_api_pre_request_trim") as trim,
            patch.object(type(app_settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
        ):
            with patched_client() as client:
                response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        trim.assert_not_called()

    def test_non_api_request_does_not_trigger_pre_request_trim(self):
        with (
            patch("app.main._maybe_schedule_public_api_pre_request_trim") as trim,
            patch.object(type(app_settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
        ):
            with patched_client() as client:
                response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        trim.assert_not_called()

    def test_public_api_request_triggers_pre_request_trim_scheduler(self):
        async def _trim(reason: str):
            return {"attempted": False, "trimmed": False, "reason": reason}

        with (
            patch("app.main._maybe_schedule_public_api_pre_request_trim", side_effect=_trim) as trim,
            patch.object(type(app_settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
        ):
            with patched_client() as client:
                response = client.get("/api/countries")

        self.assertEqual(response.status_code, 200)
        trim.assert_called_once()


class MainPreRequestMemoryTrimTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main_module._public_api_pre_request_trim_task = None

    async def asyncTearDown(self):
        task = main_module._public_api_pre_request_trim_task
        if task is not None and not task.done():
            await asyncio.wait_for(task, timeout=1.0)
        main_module._public_api_pre_request_trim_task = None

    async def test_pre_request_trim_timeout_does_not_wait_for_slow_trim_completion(self):
        def _slow_trim(reason: str):
            time.sleep(0.3)
            return {"attempted": True, "trimmed": True, "reason": reason}

        started_at = time.perf_counter()
        with patch("app.main.maybe_trim_process_memory", side_effect=_slow_trim):
            await main_module._maybe_schedule_public_api_pre_request_trim("pre:countries")
            elapsed = time.perf_counter() - started_at
            await asyncio.sleep(0.35)

        self.assertLess(
            elapsed,
            main_module.PUBLIC_API_PRE_REQUEST_TRIM_TIMEOUT_SECONDS + 0.08,
        )
        self.assertIsNone(main_module._public_api_pre_request_trim_task)

    async def test_pre_request_trim_reuses_inflight_task_without_waiting_again(self):
        release = threading.Event()

        def _slow_trim(reason: str):
            release.wait(timeout=1.0)
            return {"attempted": True, "trimmed": True, "reason": reason}

        with patch("app.main.maybe_trim_process_memory", side_effect=_slow_trim) as trim:
            await main_module._maybe_schedule_public_api_pre_request_trim("pre:first")
            started_at = time.perf_counter()
            await main_module._maybe_schedule_public_api_pre_request_trim("pre:second")
            elapsed = time.perf_counter() - started_at
            release.set()
            await asyncio.sleep(0.05)

        self.assertEqual(trim.call_count, 1)
        self.assertLess(elapsed, 0.05)
