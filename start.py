from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dev_runtime import (
    IS_WINDOWS,
    ROOT,
    display_path,
    ensure_runtime_dir,
    find_project_python,
    frontend_dev_command,
)


def run_check() -> int:
    backend_main = ROOT / "backend" / "app" / "main.py"
    frontend_package = ROOT / "frontend" / "package.json"
    backend_env = ROOT / "backend" / ".env"
    frontend_node_modules = ROOT / "frontend" / "node_modules"
    python_path = find_project_python()
    frontend_command = frontend_dev_command()

    failures: list[str] = []

    print("[check] 개발 런처 환경 점검")

    if python_path:
        print(f"[ok] 가상환경 Python: {python_path}")
    else:
        failures.append("가상환경 Python을 찾을 수 없습니다. `python -m venv venv`와 패키지 설치를 먼저 완료하세요.")

    if backend_main.exists():
        print(f"[ok] 백엔드 엔트리포인트: {display_path(backend_main)}")
    else:
        failures.append(f"백엔드 엔트리포인트가 없습니다: {display_path(backend_main)}")

    if frontend_package.exists():
        print(f"[ok] 프론트 패키지 설정: {display_path(frontend_package)}")
    else:
        failures.append(f"프론트 패키지 설정이 없습니다: {display_path(frontend_package)}")

    if frontend_command:
        print(f"[ok] 프론트 실행 명령 준비: {' '.join(frontend_command[:2])}")
    else:
        failures.append("프론트 실행 명령을 만들 수 없습니다. Node.js와 npm 설치를 확인하세요.")

    if backend_env.exists():
        print(f"[ok] 환경 변수 파일: {display_path(backend_env)}")
    else:
        print(f"[warn] 환경 변수 파일이 없습니다: {display_path(backend_env)}")

    if frontend_node_modules.exists():
        print(f"[ok] 프론트 의존성 디렉터리: {display_path(frontend_node_modules)}")
    else:
        print(f"[warn] node_modules가 없습니다: {display_path(frontend_node_modules)}")

    if python_path:
        probe = subprocess.run(
            [python_path, "-c", "import fastapi, uvicorn"],
            cwd=display_path(ROOT),
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


def read_log_excerpt(log_path: Path, max_lines: int = 20) -> str:
    if not log_path.exists():
        return "로그 파일이 아직 생성되지 않았습니다."

    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "로그 파일을 읽지 못했습니다."

    if not content:
        return "로그 내용이 아직 없습니다."

    excerpt = content[-max_lines:]
    return "\n".join(excerpt)


def wait_for_http(url: str, timeout_seconds: int, proc: subprocess.Popen[str] | None, label: str, log_path: Path) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            print(f"[fail] {label} 프로세스가 조기에 종료되었습니다. 종료 코드: {proc.returncode}")
            print(f"[hint] 로그 확인: {display_path(log_path)}")
            print(read_log_excerpt(log_path))
            return False

        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            time.sleep(1)

    print(f"[fail] {label} 준비 대기 시간이 초과되었습니다: {url}")
    print(f"[hint] 로그 확인: {display_path(log_path)}")
    print(read_log_excerpt(log_path))
    return False


def launch_services() -> int:
    python_path = find_project_python()
    frontend_command = frontend_dev_command()

    if not python_path:
        print("[fail] 가상환경 Python을 찾지 못했습니다. 먼저 `python -m venv venv`와 패키지 설치를 완료하세요.")
        return 1

    if not frontend_command:
        print("[fail] 프론트 실행 명령을 만들지 못했습니다. Node.js와 npm 설치를 확인하세요.")
        return 1

    backend_dir = ROOT / "backend"
    frontend_dir = ROOT / "frontend"
    runtime_dir = ensure_runtime_dir()
    backend_log = runtime_dir / "backend.log"
    frontend_log = runtime_dir / "frontend.log"

    backend_proc: subprocess.Popen[str] | None = None
    frontend_proc: subprocess.Popen[str] | None = None
    backend_stream = None
    frontend_stream = None

    try:
        backend_stream = backend_log.open("w", encoding="utf-8")
        frontend_stream = frontend_log.open("w", encoding="utf-8")

        print("[start] Stock Predict 개발 서버를 시작합니다.")
        print(f"[start] 로그 위치: {display_path(runtime_dir)}")

        backend_proc = subprocess.Popen(
            [python_path, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
            cwd=display_path(backend_dir),
            stdout=backend_stream,
            stderr=subprocess.STDOUT,
        )

        print("[start] 백엔드 준비 대기 중...")
        if not wait_for_http("http://127.0.0.1:8000/api/health", 25, backend_proc, "백엔드", backend_log):
            return 1

        frontend_proc = subprocess.Popen(
            frontend_command,
            cwd=display_path(frontend_dir),
            stdout=frontend_stream,
            stderr=subprocess.STDOUT,
        )

        print("[start] 프론트 준비 대기 중...")
        if not wait_for_http("http://127.0.0.1:3000", 45, frontend_proc, "프론트엔드", frontend_log):
            return 1

        print("")
        print("Frontend: http://localhost:3000")
        print("Backend:  http://localhost:8000")
        print("API Docs: http://localhost:8000/docs")
        print(f"백엔드 로그: {display_path(backend_log)}")
        print(f"프론트 로그: {display_path(frontend_log)}")
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
        if frontend_stream is not None:
            frontend_stream.close()
        if backend_stream is not None:
            backend_stream.close()
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
