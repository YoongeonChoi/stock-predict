from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


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
