from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_browser_profile_dir_ignores_windows_cleanup_races(self) -> None:
        with patch.object(browser_smoke.tempfile, "TemporaryDirectory") as temporary_directory:
            browser_smoke.browser_profile_dir(prefix="stock-predict-browser-smoke-")

        temporary_directory.assert_called_once_with(
            prefix="stock-predict-browser-smoke-",
            ignore_cleanup_errors=True,
        )

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

    def test_dump_dom_uses_http_fallback_when_edge_stdout_is_empty(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        with patch.object(browser_smoke.subprocess, "run", return_value=completed):
            with patch.object(browser_smoke, "fetch_server_html", return_value="<html>fallback</html>") as fallback:
                html = browser_smoke.dump_dom(
                    browser="browser",
                    url="https://example.com",
                    virtual_time_budget_ms=18000,
                    viewport=(390, 844),
                    command_timeout_seconds=21,
                )

        self.assertEqual(html, "<html>fallback</html>")
        fallback.assert_called_once_with("https://example.com", 21)

    def test_save_screenshot_requires_non_empty_output_file(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "screen.png"
            with patch.object(browser_smoke.subprocess, "run", return_value=completed):
                ok = browser_smoke.save_screenshot(
                    browser="browser",
                    url="https://example.com",
                    destination=destination,
                    virtual_time_budget_ms=18000,
                    viewport=(390, 844),
                    command_timeout_seconds=21,
                )

        self.assertFalse(ok)

    def test_save_screenshot_removes_stale_output_before_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "screen.png"
            destination.write_bytes(b"stale" * 1024)
            with patch.object(
                browser_smoke.subprocess,
                "run",
                side_effect=browser_smoke.subprocess.TimeoutExpired(cmd=["browser"], timeout=21),
            ):
                ok = browser_smoke.save_screenshot(
                    browser="browser",
                    url="https://example.com",
                    destination=destination,
                    virtual_time_budget_ms=18000,
                    viewport=(390, 844),
                    command_timeout_seconds=21,
                )

        self.assertFalse(ok)
        self.assertFalse(destination.exists())

    def test_run_check_passes_dom_contract_when_screenshot_is_unavailable(self) -> None:
        check = browser_smoke.BrowserCheck(
            name="test",
            path="/",
            required_texts=("required",),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with patch.object(browser_smoke, "dump_dom", return_value="<html>required</html>"):
                with patch.object(browser_smoke, "save_screenshot", return_value=False):
                    ok, detail = browser_smoke.run_check(
                        browser="browser",
                        base_url="https://example.com",
                        check=check,
                        attempts=1,
                        retry_delay=0.5,
                        virtual_time_budget_ms=18000,
                        output_dir=output_dir,
                        viewport=(390, 844),
                        command_timeout_seconds=30.0,
                    )

        self.assertTrue(ok)
        self.assertIn("DOM ok; screenshot unavailable", detail)

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
