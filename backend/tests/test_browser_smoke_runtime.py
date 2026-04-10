from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_browser_smoke_module():
    root = Path(__file__).resolve().parents[2]
    scripts_dir = root / "scripts"
    module_path = scripts_dir / "browser_smoke.py"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("browser_smoke_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load browser_smoke.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


browser_smoke = _load_browser_smoke_module()


class BrowserSmokeRuntimeTests(unittest.TestCase):
    def test_resolve_command_timeout_respects_virtual_budget(self) -> None:
        timeout_seconds = browser_smoke.resolve_command_timeout_seconds(18000, 5.0)

        self.assertGreaterEqual(timeout_seconds, 28.0)

    def test_dump_dom_timeout_raises_runtime_error(self) -> None:
        with patch.object(
            browser_smoke.subprocess,
            "run",
            side_effect=browser_smoke.subprocess.TimeoutExpired(cmd=["browser"], timeout=21),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                browser_smoke.dump_dom(
                    browser="browser",
                    url="https://example.com",
                    virtual_time_budget_ms=18000,
                    viewport=(390, 844),
                    command_timeout_seconds=21,
                )

    def test_run_check_stops_when_deadline_is_already_exceeded(self) -> None:
        check = browser_smoke.BrowserCheck(
            name="test",
            path="/",
            required_texts=("required",),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with patch.object(browser_smoke, "dump_dom") as dump_dom_mock:
                ok, detail = browser_smoke.run_check(
                    browser="browser",
                    base_url="https://example.com",
                    check=check,
                    attempts=6,
                    retry_delay=0.5,
                    virtual_time_budget_ms=18000,
                    output_dir=output_dir,
                    viewport=(390, 844),
                    command_timeout_seconds=30.0,
                    deadline_monotonic=browser_smoke.time.monotonic() - 1.0,
                )

        self.assertFalse(ok)
        self.assertEqual(detail, "browser smoke deadline exceeded")
        dump_dom_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
