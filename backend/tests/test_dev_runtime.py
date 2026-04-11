from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_dev_runtime():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "dev_runtime.py"
    spec = importlib.util.spec_from_file_location("dev_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load dev_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev_runtime = _load_dev_runtime()


class DevRuntimeTests(unittest.TestCase):
    def test_normalize_strips_extended_local_prefix(self) -> None:
        raw = r"\\?\C:\clone_repo\stock-predict"
        self.assertEqual(dev_runtime.normalize_windows_path(raw), r"C:\clone_repo\stock-predict")

    def test_normalize_strips_powershell_provider_prefix(self) -> None:
        raw = r"Microsoft.PowerShell.Core\FileSystem::\\?\C:\clone_repo\stock-predict"
        self.assertEqual(dev_runtime.normalize_windows_path(raw), r"C:\clone_repo\stock-predict")

    def test_normalize_unc_extended_path(self) -> None:
        raw = r"\\?\UNC\server\share\repo"
        self.assertEqual(dev_runtime.normalize_windows_path(raw), r"\\server\share\repo")

    def test_runtime_dir_is_under_repo_root(self) -> None:
        runtime_dir = dev_runtime.ensure_runtime_dir()
        self.assertEqual(runtime_dir.name, ".run")

    def test_find_project_python_prefers_repo_local_venv(self) -> None:
        with (
            patch.object(dev_runtime, "local_project_python_command", return_value=["venv-python"]),
            patch.object(dev_runtime, "current_python_command", return_value=["current-python"]),
            patch.object(dev_runtime, "windows_py_launcher_command", return_value=["py", "-3"]),
            patch.object(dev_runtime, "python_command_runs", side_effect=lambda command: command == ["venv-python"]),
        ):
            self.assertEqual(dev_runtime.find_project_python(), ["venv-python"])

    def test_find_project_python_falls_back_to_current_python(self) -> None:
        with (
            patch.object(dev_runtime, "local_project_python_command", return_value=["venv-python"]),
            patch.object(dev_runtime, "current_python_command", return_value=["current-python"]),
            patch.object(dev_runtime, "windows_py_launcher_command", return_value=["py", "-3"]),
            patch.object(dev_runtime, "python_command_runs", side_effect=lambda command: command == ["current-python"]),
        ):
            self.assertEqual(dev_runtime.find_project_python(), ["current-python"])

    def test_find_project_python_falls_back_to_windows_py_launcher(self) -> None:
        with (
            patch.object(dev_runtime, "local_project_python_command", return_value=["venv-python"]),
            patch.object(dev_runtime, "current_python_command", return_value=["current-python"]),
            patch.object(dev_runtime, "windows_py_launcher_command", return_value=["py", "-3"]),
            patch.object(dev_runtime, "python_command_runs", side_effect=lambda command: command == ["py", "-3"]),
        ):
            self.assertEqual(dev_runtime.find_project_python(), ["py", "-3"])

    def test_frontend_build_command_prefers_local_runner(self) -> None:
        with (
            patch.object(dev_runtime, "local_frontend_runner", return_value=["frontend-next", "build"]),
            patch.object(dev_runtime, "resolve_node_runner") as resolve_node_runner,
        ):
            self.assertEqual(dev_runtime.frontend_build_command(), ["frontend-next", "build"])
            resolve_node_runner.assert_not_called()

    def test_frontend_typecheck_command_falls_back_to_npx(self) -> None:
        with (
            patch.object(dev_runtime, "local_frontend_runner", return_value=None),
            patch.object(dev_runtime, "resolve_node_runner", return_value=["npx", "tsc", "--noEmit"]) as resolve_node_runner,
        ):
            self.assertEqual(dev_runtime.frontend_typecheck_command(), ["npx", "tsc", "--noEmit"])
            resolve_node_runner.assert_called_once_with("npx", "tsc", "--noEmit")

    def test_resolve_node_runner_falls_back_to_standard_windows_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir)
            (install_dir / "node.exe").write_text("", encoding="utf-8")
            cli_dir = install_dir / "node_modules" / "npm" / "bin"
            cli_dir.mkdir(parents=True)
            (cli_dir / "npm-cli.js").write_text("", encoding="utf-8")

            with (
                patch.object(dev_runtime, "IS_WINDOWS", True),
                patch.object(dev_runtime, "find_command", return_value=None),
                patch.object(dev_runtime, "standard_windows_node_install_dirs", return_value=(install_dir,)),
            ):
                self.assertEqual(
                    dev_runtime.resolve_node_runner("npm", "run", "build"),
                    [str(install_dir / "node.exe"), str(cli_dir / "npm-cli.js"), "run", "build"],
                )

    def test_local_frontend_runner_resolves_windows_cmd_shim_with_standard_node(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            frontend_bin = root_dir / "frontend" / "node_modules" / ".bin"
            frontend_bin.mkdir(parents=True)
            shim_path = frontend_bin / "next.cmd"
            shim_path.write_text(
                '@ECHO off\n"%dp0%\\..\\next\\dist\\bin\\next" %*\n',
                encoding="utf-8",
            )
            target_script = root_dir / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
            target_script.parent.mkdir(parents=True)
            target_script.write_text("", encoding="utf-8")

            install_dir = root_dir / "node-install"
            install_dir.mkdir()
            (install_dir / "node.exe").write_text("", encoding="utf-8")

            with (
                patch.object(dev_runtime, "IS_WINDOWS", True),
                patch.object(dev_runtime, "FRONTEND_BIN_DIR", frontend_bin),
                patch.object(dev_runtime, "standard_windows_node_install_dirs", return_value=(install_dir,)),
            ):
                self.assertEqual(
                    dev_runtime.local_frontend_runner("next", "build"),
                    [str(install_dir / "node.exe"), str(target_script), "build"],
                )
