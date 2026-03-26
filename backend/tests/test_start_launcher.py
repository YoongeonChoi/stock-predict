from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _load_start_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "start.py"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("start_launcher", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load start.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


start_launcher = _load_start_module()


class StartLauncherTests(unittest.TestCase):
    def test_prepare_services_for_launch_stops_running_servers_automatically(self) -> None:
        running_status = {
            "backend": {"pid": 111, "running": True, "healthy": True, "log": Path("backend.log")},
            "frontend": {"pid": 222, "running": True, "healthy": True, "log": Path("frontend.log")},
        }

        with (
            patch.object(start_launcher, "read_status", return_value=running_status),
            patch.object(start_launcher, "stop_services", return_value=0) as stop_services,
            patch.object(start_launcher, "print_status") as print_status,
        ):
            self.assertTrue(start_launcher.prepare_services_for_launch())
            print_status.assert_called_once()
            stop_services.assert_called_once()

    def test_launch_services_restarts_after_cleanup_and_starts_processes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_dir = Path(tmpdir)
            paths = {
                "dir": runtime_dir,
                "backend_log": runtime_dir / "backend.log",
                "frontend_log": runtime_dir / "frontend.log",
                "backend_pid": runtime_dir / "backend.pid",
                "frontend_pid": runtime_dir / "frontend.pid",
            }

            backend_proc = SimpleNamespace(pid=111)
            frontend_proc = SimpleNamespace(pid=222)

            with (
                patch.object(start_launcher, "find_project_python", return_value="python"),
                patch.object(start_launcher, "frontend_dev_command", return_value=["npm", "run", "dev"]),
                patch.object(start_launcher, "prepare_services_for_launch", return_value=True) as prepare,
                patch.object(start_launcher, "runtime_paths", return_value=paths),
                patch.object(start_launcher, "wait_for_http", return_value=True),
                patch.object(start_launcher, "write_pid") as write_pid,
                patch.object(start_launcher.subprocess, "Popen", side_effect=[backend_proc, frontend_proc]),
            ):
                self.assertEqual(start_launcher.launch_services(), 0)

            prepare.assert_called_once()
            self.assertEqual(write_pid.call_args_list[0].args, (paths["backend_pid"], 111))
            self.assertEqual(write_pid.call_args_list[1].args, (paths["frontend_pid"], 222))


if __name__ == "__main__":
    unittest.main()
