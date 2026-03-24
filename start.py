from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
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


def find_npm() -> str | None:
    if IS_WINDOWS:
        return shutil.which("npm.cmd") or shutil.which("npm")
    return shutil.which("npm")


def run_check() -> int:
    backend_main = ROOT / "backend" / "app" / "main.py"
    frontend_package = ROOT / "frontend" / "package.json"
    backend_env = ROOT / "backend" / ".env"
    frontend_node_modules = ROOT / "frontend" / "node_modules"
    python_path = find_project_python()
    npm_path = find_npm()

    failures: list[str] = []

    print("[check] 개발 런처 환경 점검")

    if python_path:
        print(f"[ok] 가상환경 Python: {python_path}")
    else:
        failures.append(f"가상환경 Python을 찾을 수 없습니다: {WINDOWS_PYTHON if IS_WINDOWS else POSIX_PYTHON}")

    if backend_main.exists():
        print(f"[ok] 백엔드 엔트리포인트: {backend_main}")
    else:
        failures.append(f"백엔드 엔트리포인트가 없습니다: {backend_main}")

    if frontend_package.exists():
        print(f"[ok] 프론트 패키지 설정: {frontend_package}")
    else:
        failures.append(f"프론트 패키지 설정이 없습니다: {frontend_package}")

    if npm_path:
        print(f"[ok] npm 실행 파일: {npm_path}")
    else:
        failures.append("npm 실행 파일을 찾을 수 없습니다. Node.js 설치를 확인하세요.")

    if backend_env.exists():
        print(f"[ok] 환경 변수 파일: {backend_env}")
    else:
        print(f"[warn] 환경 변수 파일이 없습니다: {backend_env}")

    if frontend_node_modules.exists():
        print(f"[ok] 프론트 의존성 디렉터리: {frontend_node_modules}")
    else:
        print(f"[warn] node_modules가 없습니다: {frontend_node_modules}")

    if python_path:
        probe = subprocess.run(
            [python_path, "-c", "import fastapi, uvicorn"],
            cwd=str(ROOT),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            print("[ok] 백엔드 핵심 패키지 import 확인")
        else:
            failures.append("가상환경에 fastapi/uvicorn이 준비되지 않았습니다. backend/requirements.txt 설치를 확인하세요.")

    if failures:
        print("[fail] 시작 전 점검에서 문제가 발견되었습니다.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("[done] 시작 전 점검 완료")
    return 0


def build_windows_command(workdir: Path, inner_command: str) -> list[str]:
    return ["cmd.exe", "/d", "/k", f'cd /d "{workdir}" && {inner_command}']


def kill_process_tree(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return

    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def launch_services() -> int:
    python_path = find_project_python()
    npm_path = find_npm()

    if not python_path:
        print("[fail] 가상환경 Python을 찾지 못했습니다. 먼저 `python -m venv venv`와 패키지 설치를 완료하세요.")
        return 1

    if not npm_path:
        print("[fail] npm을 찾지 못했습니다. Node.js 설치를 확인하세요.")
        return 1

    backend_dir = ROOT / "backend"
    frontend_dir = ROOT / "frontend"

    backend_proc: subprocess.Popen[str] | None = None
    frontend_proc: subprocess.Popen[str] | None = None

    try:
        print("[start] Stock Predict 개발 서버를 시작합니다.")
        if IS_WINDOWS:
            backend_inner = f'"{python_path}" -m uvicorn app.main:app --reload --port 8000'
            backend_proc = subprocess.Popen(
                build_windows_command(backend_dir, backend_inner),
                cwd=str(ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            backend_proc = subprocess.Popen(
                [python_path, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
                cwd=str(backend_dir),
            )

        print("[start] 백엔드 준비 대기 중...")
        time.sleep(3)

        if IS_WINDOWS:
            frontend_inner = f'"{npm_path}" run dev'
            frontend_proc = subprocess.Popen(
                build_windows_command(frontend_dir, frontend_inner),
                cwd=str(ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            frontend_proc = subprocess.Popen(
                [npm_path, "run", "dev"],
                cwd=str(frontend_dir),
            )

        print("")
        print("Frontend: http://localhost:3000")
        print("Backend:  http://localhost:8000")
        print("API Docs: http://localhost:8000/docs")
        print("")
        input("Enter를 누르면 백엔드와 프론트를 함께 종료합니다...")
        return 0
    except KeyboardInterrupt:
        print("")
        print("[stop] 사용자 요청으로 서버를 종료합니다.")
        return 0
    finally:
        kill_process_tree(frontend_proc)
        kill_process_tree(backend_proc)
        print("[done] 개발 서버를 정리했습니다.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock Predict 개발 서버 런처")
    parser.add_argument("--check", action="store_true", help="개발 서버 시작 전에 환경만 점검합니다.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.check:
        return run_check()
    return launch_services()


if __name__ == "__main__":
    raise SystemExit(main())
