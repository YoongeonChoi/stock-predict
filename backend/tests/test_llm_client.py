from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class LlmClientLazyImportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._previous_openai = sys.modules.pop("openai", None)
        self._previous_module = sys.modules.pop("app.analysis.llm_client", None)

    def tearDown(self) -> None:
        sys.modules.pop("app.analysis.llm_client", None)
        sys.modules.pop("openai", None)
        if self._previous_module is not None:
            sys.modules["app.analysis.llm_client"] = self._previous_module
        if self._previous_openai is not None:
            sys.modules["openai"] = self._previous_openai

    async def test_import_does_not_eagerly_load_openai(self) -> None:
        llm_client = importlib.import_module("app.analysis.llm_client")

        self.assertNotIn("openai", sys.modules)
        self.assertTrue(callable(llm_client.ask_json))

    async def test_missing_api_key_returns_without_importing_openai(self) -> None:
        llm_client = importlib.import_module("app.analysis.llm_client")

        with patch.object(llm_client, "get_settings", return_value=type("S", (), {"openai_api_key": "", "openai_model": "gpt-4o"})()):
            payload = await llm_client.ask_json("system", "user")

        self.assertNotIn("openai", sys.modules)
        self.assertEqual(payload.get("error_code"), "SP-1001")


if __name__ == "__main__":
    unittest.main()
