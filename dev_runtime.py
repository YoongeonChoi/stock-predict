from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import re
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
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_BIN_DIR = FRONTEND_DIR / "node_modules" / ".bin"


def display_path(value: str | Path) -> str:
    return normalize_windows_path(value)


def display_command(command: list[str]) -> str:
    resolved = [display_path(part) for part in command]
    if IS_WINDOWS:
        return subprocess.list2cmdline(resolved)
    return shlex.join(resolved)


def local_project_python_command() -> list[str] | None:
    candidate = WINDOWS_PYTHON if IS_WINDOWS else POSIX_PYTHON
    if candidate.exists():
        return [display_path(candidate)]
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


def current_python_command() -> list[str] | None:
    current = getattr(sys, "executable", "") or ""
    if not current:
        return None
    current_path = normalized_path(current)
    if current_path.exists():
        return [display_path(current_path)]
    return None


def windows_py_launcher_command() -> list[str] | None:
    if not IS_WINDOWS:
        return None
    launcher = find_command("py.exe", "py")
    if launcher:
        return [launcher, "-3"]
    return None


def python_command_runs(command: list[str]) -> bool:
    try:
        completed = subprocess.run(
            [*command, "-c", "import sys"],
            cwd=display_path(ROOT),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return completed.returncode == 0


def python_command_supports_modules(command: list[str], *modules: str) -> bool:
    if not modules:
        return python_command_runs(command)
    script = "import " + ", ".join(modules)
    try:
        completed = subprocess.run(
            [*command, "-c", script],
            cwd=display_path(ROOT),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return completed.returncode == 0


def find_project_python() -> list[str] | None:
    candidates: list[list[str]] = []
    for candidate in (
        local_project_python_command(),
        current_python_command(),
        windows_py_launcher_command(),
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        if python_command_runs(candidate):
            return candidate
    return None


def local_frontend_runner(command_name: str, *args: str) -> list[str] | None:
    suffix = ".cmd" if IS_WINDOWS else ""
    candidate = FRONTEND_BIN_DIR / f"{command_name}{suffix}"
    if not candidate.exists():
        return None
    if IS_WINDOWS:
        shim_command = resolve_windows_cmd_shim(candidate, *args)
        if shim_command:
            return shim_command
    return [display_path(candidate), *args]


def standard_windows_node_install_dirs() -> tuple[Path, ...]:
    if not IS_WINDOWS:
        return ()

    candidates = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs",
        Path(os.environ.get("LocalAppData", "")) / "Programs" / "nodejs",
    )
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        rendered = normalize_windows_path(candidate)
        if not rendered or rendered in seen:
            continue
        seen.add(rendered)
        deduped.append(normalized_path(candidate))
    return tuple(deduped)


def standard_windows_node_runner(command_name: str, *args: str) -> list[str] | None:
    if not IS_WINDOWS:
        return None

    cli_name = {"npm": "npm-cli.js", "npx": "npx-cli.js"}.get(command_name)
    for install_dir in standard_windows_node_install_dirs():
        node_exe = install_dir / "node.exe"
        wrapper = install_dir / f"{command_name}.cmd"
        if cli_name:
            cli_script = install_dir / "node_modules" / "npm" / "bin" / cli_name
            if node_exe.exists() and cli_script.exists():
                return [display_path(node_exe), display_path(cli_script), *args]
        if wrapper.exists():
            return [display_path(wrapper), *args]
    return None


def resolve_windows_cmd_shim(script_path: Path, *args: str) -> list[str] | None:
    if not IS_WINDOWS or script_path.suffix.lower() != ".cmd" or not script_path.exists():
        return None

    try:
        content = script_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    match = re.search(r'"%dp0%\\\.\.\\([^"]+)"', content)
    if not match:
        return None

    target_rel = match.group(1).replace("\\", os.sep)
    target_script = normalized_path(script_path.parent.parent / target_rel)
    if not target_script.exists():
        return None

    node_exe = script_path.with_name("node.exe")
    if not node_exe.exists():
        for install_dir in standard_windows_node_install_dirs():
            candidate = install_dir / "node.exe"
            if candidate.exists():
                node_exe = candidate
                break

    if not node_exe.exists():
        return None

    return [display_path(node_exe), display_path(target_script), *args]


def resolve_node_runner(command_name: str, *args: str) -> list[str] | None:
    if IS_WINDOWS:
        script_path = find_command(f"{command_name}.cmd", command_name)
    else:
        script_path = find_command(command_name)

    if not script_path:
        return standard_windows_node_runner(command_name, *args)

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
    return local_frontend_runner("next", "dev") or resolve_node_runner("npm", "run", "dev")


def frontend_build_command() -> list[str] | None:
    return local_frontend_runner("next", "build") or resolve_node_runner("npm", "run", "build")


def frontend_typecheck_command() -> list[str] | None:
    return local_frontend_runner("tsc", "--noEmit") or resolve_node_runner("npx", "tsc", "--noEmit")
