from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_verify_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "verify.py"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("verify_runner", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load verify.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify_runner = _load_verify_module()


class VerifyRuntimeTests(unittest.TestCase):
    def test_requirement_to_import_name_normalizes_known_packages(self) -> None:
        self.assertEqual(verify_runner.requirement_to_import_name("pydantic-settings"), "pydantic_settings")
        self.assertEqual(verify_runner.requirement_to_import_name("python-dotenv"), "dotenv")
        self.assertEqual(verify_runner.requirement_to_import_name("fpdf2"), "fpdf")
        self.assertEqual(verify_runner.requirement_to_import_name("uvicorn[standard]"), "uvicorn")

    def test_full_sweep_enables_optional_stages(self) -> None:
        args = verify_runner.parse_args(["--full-sweep"])
        stages = verify_runner.resolve_stage_selection(args)

        self.assertTrue(stages.run_frontend_checks)
        self.assertTrue(stages.run_live_api_smoke)
        self.assertTrue(stages.run_browser_smoke)
        self.assertTrue(stages.run_deployed_site_smoke)
        self.assertTrue(stages.run_auth_write_smoke)

    def test_deployed_only_does_not_force_local_browser_smoke(self) -> None:
        args = verify_runner.parse_args(["--deployed-site-smoke"])
        stages = verify_runner.resolve_stage_selection(args)

        self.assertFalse(stages.run_browser_smoke)
        self.assertTrue(stages.run_deployed_site_smoke)

    def test_skip_frontend_only_disables_frontend_build_and_typecheck(self) -> None:
        args = verify_runner.parse_args(["--skip-frontend", "--full-sweep"])
        stages = verify_runner.resolve_stage_selection(args)

        self.assertFalse(stages.run_frontend_checks)
        self.assertTrue(stages.run_live_api_smoke)
        self.assertTrue(stages.run_browser_smoke)
        self.assertTrue(stages.run_deployed_site_smoke)
        self.assertTrue(stages.run_auth_write_smoke)

    def test_backend_import_probe_list_includes_requests_dependency(self) -> None:
        probes = verify_runner.load_backend_import_probes()

        self.assertIn("requests", probes)
        self.assertIn("httpx", probes)

    def test_parse_args_supports_allow_parallel(self) -> None:
        args = verify_runner.parse_args(["--allow-parallel"])

        self.assertTrue(args.allow_parallel)

    def test_browser_smoke_command_uses_expanded_viewport_matrix_budget(self) -> None:
        command = verify_runner.build_browser_smoke_command(["python"], "https://www.yoongeon.xyz")

        max_total_index = command.index("--max-total-seconds")
        self.assertEqual(
            command[max_total_index + 1],
            str(verify_runner.BROWSER_SMOKE_VIEWPORT_MATRIX_MAX_TOTAL_SECONDS),
        )
        self.assertIn("--viewport-matrix", command)

    def test_warm_browser_routes_command_targets_requested_base_url(self) -> None:
        command = verify_runner.build_warm_browser_routes_command(["python"], "https://www.yoongeon.xyz")

        self.assertEqual(command[:2], ["python", "-c"])
        self.assertIn("warm_browser_routes('https://www.yoongeon.xyz')", command[2])

    def test_acquire_verify_lock_blocks_second_active_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".verify.lock"

            with patch.object(verify_runner, "VERIFY_LOCK_PATH", lock_path):
                with verify_runner.acquire_verify_lock():
                    with self.assertRaisesRegex(SystemExit, "Another verify.py run appears to be active"):
                        with verify_runner.acquire_verify_lock():
                            self.fail("nested lock acquisition should not succeed")

            self.assertFalse(lock_path.exists())

    def test_acquire_verify_lock_replaces_stale_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".verify.lock"
            lock_path.write_text('{"pid": 999, "started_at": "stale"}', encoding="utf-8")
            stale_time = verify_runner.time.time() - verify_runner.VERIFY_LOCK_STALE_SECONDS - 5
            verify_runner.os.utime(lock_path, (stale_time, stale_time))

            with patch.object(verify_runner, "VERIFY_LOCK_PATH", lock_path):
                with verify_runner.acquire_verify_lock():
                    self.assertTrue(lock_path.exists())
                    metadata = verify_runner._read_lock_metadata(lock_path)
                    self.assertEqual(metadata["pid"], verify_runner.os.getpid())

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
