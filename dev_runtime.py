from __future__ import annotations

import os
import shutil
from pathlib import Path


IS_WINDOWS = os.name == "nt"


def normalize_windows_path(value: str | Path) -> str:
    raw = str(value)

    if raw.startswith("Microsoft.PowerShell.Core\\FileSystem::"):
        raw = raw.split("::", 1)[1]

    if raw.startswith("\\\\?\\UNC\\"):
        return "\\\\" + raw[8:]

    if raw.startswith("\\\\?\\") or raw.startswith("\\\\.\\"):
        return raw[4:]

    return raw


def normalized_path(value: str | Path) -> Path:
    return Path(normalize_windows_path(value))


ROOT = normalized_path(Path(__file__).resolve().parent)
WINDOWS_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
POSIX_PYTHON = ROOT / "venv" / "bin" / "python"
RUNTIME_DIR = ROOT / ".run"


def display_path(value: str | Path) -> str:
    return normalize_windows_path(value)


def find_project_python() -> str | None:
    candidate = WINDOWS_PYTHON if IS_WINDOWS else POSIX_PYTHON
    if candidate.exists():
        return display_path(candidate)
    return None


def find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return display_path(resolved)
    return None


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR


def resolve_node_runner(command_name: str, *args: str) -> list[str] | None:
    if IS_WINDOWS:
        script_path = find_command(f"{command_name}.cmd", command_name)
    else:
        script_path = find_command(command_name)

    if not script_path:
        return None

    if IS_WINDOWS:
        script = normalized_path(script_path)
        node_exe = script.with_name("node.exe")
        cli_name = {"npm": "npm-cli.js", "npx": "npx-cli.js"}.get(command_name)
        if cli_name:
            cli_script = script.parent / "node_modules" / "npm" / "bin" / cli_name
            if node_exe.exists() and cli_script.exists():
                return [display_path(node_exe), display_path(cli_script), *args]

    return [script_path, *args]


def frontend_dev_command() -> list[str] | None:
    return resolve_node_runner("npm", "run", "dev")


def frontend_build_command() -> list[str] | None:
    return resolve_node_runner("npm", "run", "build")


def frontend_typecheck_command() -> list[str] | None:
    return resolve_node_runner("npx", "tsc", "--noEmit")
