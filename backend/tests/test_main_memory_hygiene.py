import unittest
from unittest.mock import PropertyMock, patch

from app.main import settings as app_settings
from tests.client_helpers import patched_client


class MainMemoryHygieneMiddlewareTests(unittest.TestCase):
    def test_public_api_get_triggers_pre_request_trim(self):
        with (
            patch("app.main.maybe_trim_process_memory") as trim,
            patch.object(type(app_settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
        ):
            with patched_client() as client:
                response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        trim.assert_called_once()
        self.assertTrue(trim.call_args.args[0].startswith("pre:health"))

    def test_non_api_request_does_not_trigger_pre_request_trim(self):
        with (
            patch("app.main.maybe_trim_process_memory") as trim,
            patch.object(type(app_settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
        ):
            with patched_client() as client:
                response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        trim.assert_not_called()
