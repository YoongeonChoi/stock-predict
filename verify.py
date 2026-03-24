from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
WINDOWS_PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
POSIX_PYTHON = ROOT / "venv" / "bin" / "python"


def find_project_python() -> str | None:
    candidate = WINDOWS_PYTHON if IS_WINDOWS else POSIX_PYTHON
    if candidate.exists():
        return str(candidate)
    return None


def find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def run_step(label: str, command: list[str], cwd: Path) -> None:
    print(f"[verify] {label}")
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def windows_batch(script_path: str, *args: str) -> list[str]:
    return ["cmd.exe", "/d", "/c", "call", script_path, *args]


def windows_node_cli(script_path: str, cli_filename: str, *args: str) -> list[str] | None:
    script = Path(script_path)
    node_exe = script.with_name("node.exe")
    cli_script = script.parent / "node_modules" / "npm" / "bin" / cli_filename
    if node_exe.exists() and cli_script.exists():
        return [str(node_exe), str(cli_script), *args]
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock Predict 검증 런처")
    parser.add_argument("--skip-frontend", action="store_true", help="프론트 검증을 건너뜁니다.")
    parser.add_argument("--live-api-smoke", action="store_true", help="주요 API를 실호출 기준으로 점검합니다.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    python_path = find_project_python()
    npm_path = find_command("npm.cmd", "npm") if IS_WINDOWS else find_command("npm")
    npx_path = find_command("npx.cmd", "npx") if IS_WINDOWS else find_command("npx")

    if not python_path:
        raise SystemExit(f"가상환경 Python을 찾을 수 없습니다: {WINDOWS_PYTHON if IS_WINDOWS else POSIX_PYTHON}")

    if not npm_path:
        raise SystemExit("npm 실행 파일을 찾을 수 없습니다.")

    if not npx_path:
        raise SystemExit("npx 실행 파일을 찾을 수 없습니다.")

    run_step("Launcher check", [python_path, str(ROOT / "start.py"), "--check"], ROOT)
    run_step("Backend compileall", [python_path, "-m", "compileall", "app"], ROOT / "backend")
    run_step("Backend unittest", [python_path, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "backend")

    if args.live_api_smoke:
        run_step("Backend live API smoke", [python_path, "scripts/live_api_smoke.py"], ROOT / "backend")

    if not args.skip_frontend:
        if IS_WINDOWS:
            npm_build_command = windows_node_cli(npm_path, "npm-cli.js", "run", "build") or windows_batch(npm_path, "run", "build")
            npx_typecheck_command = windows_node_cli(npx_path, "npx-cli.js", "tsc", "--noEmit") or windows_batch(npx_path, "tsc", "--noEmit")
            run_step("Frontend build", npm_build_command, ROOT / "frontend")
            run_step("Frontend typecheck", npx_typecheck_command, ROOT / "frontend")
        else:
            run_step("Frontend build", [npm_path, "run", "build"], ROOT / "frontend")
            run_step("Frontend typecheck", [npx_path, "tsc", "--noEmit"], ROOT / "frontend")

    print("검증 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
