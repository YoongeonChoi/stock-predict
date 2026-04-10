from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dev_runtime import (
    IS_WINDOWS,
    ROOT,
    current_python_command,
    display_command,
    display_path,
    ensure_runtime_dir,
    find_project_python,
    frontend_dev_command,
    local_project_python_command,
    python_command_supports_modules,
    windows_py_launcher_command,
)


BACKEND_URL = "http://127.0.0.1:8000/api/health"
FRONTEND_URL = "http://127.0.0.1:3000"


def preferred_python_command() -> list[str]:
    return (
        find_project_python()
        or local_project_python_command()
        or current_python_command()
        or windows_py_launcher_command()
        or ["python"]
    )


def canonical_python_command(script_name: str, *args: str) -> str:
    python_command = preferred_python_command()
    script_path = display_path(ROOT / script_name)
    command = [*python_command, script_path, *args]
    rendered = display_command(command)
    return f"& {rendered}" if IS_WINDOWS else rendered


def runtime_paths() -> dict[str, Path]:
    runtime_dir = ensure_runtime_dir()
    return {
        "dir": runtime_dir,
        "backend_log": runtime_dir / "backend.log",
        "frontend_log": runtime_dir / "frontend.log",
        "backend_pid": runtime_dir / "backend.pid",
        "frontend_pid": runtime_dir / "frontend.pid",
    }


def read_log_excerpt(log_path: Path, max_lines: int = 20) -> str:
    if not log_path.exists():
        return "로그 파일이 아직 생성되지 않았습니다."

    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "로그 파일을 읽지 못했습니다."

    if not content:
        return "로그 내용이 아직 없습니다."

    return "\n".join(content[-max_lines:])


def write_pid(pid_path: Path, pid: int) -> None:
    pid_path.write_text(str(pid), encoding="utf-8")


def read_pid(pid_path: Path) -> int | None:
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_process_running(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False

    if IS_WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            check=False,
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_for_http(url: str, timeout_seconds: int, pid: int | None, label: str, log_path: Path) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if pid is not None and not is_process_running(pid):
            print(f"[fail] {label} 프로세스가 조기에 종료되었습니다. PID: {pid}")
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


def stop_pid(pid: int | None) -> bool:
    if not is_process_running(pid):
        return True

    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.kill(pid, signal.SIGTERM)

    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_process_running(pid):
            return True
        time.sleep(0.25)
    return not is_process_running(pid)


def check_backend_imports(python_command: list[str]) -> bool:
    return python_command_supports_modules(python_command, "fastapi", "uvicorn")


def run_check(*, skip_frontend: bool = False) -> int:
    backend_main = ROOT / "backend" / "app" / "main.py"
    frontend_package = ROOT / "frontend" / "package.json"
    backend_env = ROOT / "backend" / ".env"
    frontend_node_modules = ROOT / "frontend" / "node_modules"
    python_command = find_project_python()
    frontend_command = None if skip_frontend else frontend_dev_command()

    failures: list[str] = []

    print("[check] 개발 런처 환경 점검")
    print(f"[ok] 프로젝트 루트: {display_path(ROOT)}")
    hint_args = ["--check"]
    if skip_frontend:
        hint_args.append("--skip-frontend")
    print(f"[hint] 어디서 실행하든 아래 명령 1개만 사용하세요: {canonical_python_command('start.py', *hint_args)}")

    if python_command:
        print(f"[ok] Python 실행기: {display_command(python_command)}")
    else:
        failures.append(
            "프로젝트용 Python 실행기를 찾을 수 없습니다. "
            "우선순위는 `repo-local venv -> 현재 Python -> Windows py -3` 입니다."
        )

    if backend_main.exists():
        print(f"[ok] 백엔드 엔트리포인트: {display_path(backend_main)}")
    else:
        failures.append(f"백엔드 엔트리포인트가 없습니다: {display_path(backend_main)}")

    if frontend_package.exists():
        print(f"[ok] 프론트 패키지 설정: {display_path(frontend_package)}")
    else:
        failures.append(f"프론트 패키지 설정이 없습니다: {display_path(frontend_package)}")

    if skip_frontend:
        print("[skip] 프론트 실행 명령 점검은 건너뜁니다 (--skip-frontend)")
    elif frontend_command:
        print(f"[ok] 프론트 실행 명령 준비: {display_command(frontend_command)}")
    else:
        failures.append(
            "프론트 실행 명령을 만들 수 없습니다. "
            "우선순위는 `frontend/node_modules/.bin -> PATH npm/npx` 입니다."
        )

    if backend_env.exists():
        print(f"[ok] 환경 변수 파일: {display_path(backend_env)}")
    else:
        print(f"[warn] 환경 변수 파일이 없습니다: {display_path(backend_env)}")

    if skip_frontend:
        print("[skip] 프론트 의존성 디렉터리 점검은 건너뜁니다 (--skip-frontend)")
    elif frontend_node_modules.exists():
        print(f"[ok] 프론트 의존성 디렉터리: {display_path(frontend_node_modules)}")
    else:
        print(f"[warn] 프론트 의존성 디렉터리가 없습니다: {display_path(frontend_node_modules)}")

    if python_command:
        if check_backend_imports(python_command):
            print("[ok] 백엔드 핵심 패키지 import 확인")
        else:
            failures.append("선택된 Python 실행기에 fastapi/uvicorn이 준비되지 않았습니다. backend/requirements.txt 설치를 확인하세요.")

    if failures:
        print("[fail] 시작 전 점검에서 문제가 발견되었습니다.")
        for item in failures:
            print(f" - {item}")
        return 1

    print("[done] 시작 전 점검 완료")
    return 0


def read_status() -> dict[str, dict[str, object]]:
    paths = runtime_paths()
    backend_pid = read_pid(paths["backend_pid"])
    frontend_pid = read_pid(paths["frontend_pid"])

    backend_running = is_process_running(backend_pid)
    frontend_running = is_process_running(frontend_pid)

    backend_healthy = False
    frontend_healthy = False

    if backend_running:
        try:
            with urllib.request.urlopen(BACKEND_URL, timeout=2) as response:
                backend_healthy = response.status == 200
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            backend_healthy = False

    if frontend_running:
        try:
            with urllib.request.urlopen(FRONTEND_URL, timeout=2) as response:
                frontend_healthy = 200 <= response.status < 500
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            frontend_healthy = False

    return {
        "backend": {
            "pid": backend_pid,
            "running": backend_running,
            "healthy": backend_healthy,
            "log": paths["backend_log"],
        },
        "frontend": {
            "pid": frontend_pid,
            "running": frontend_running,
            "healthy": frontend_healthy,
            "log": paths["frontend_log"],
        },
    }


def print_status() -> int:
    status = read_status()
    print("[status] 개발 서버 상태")
    for label, payload in status.items():
        pid = payload["pid"]
        running = "running" if payload["running"] else "stopped"
        health = "healthy" if payload["healthy"] else "not-ready"
        print(f"- {label}: {running}, {health}, pid={pid}, log={display_path(payload['log'])}")
    return 0


def stop_services() -> int:
    paths = runtime_paths()
    stopped_any = False
    failed_labels: list[str] = []

    for label, pid_key in (("frontend", "frontend_pid"), ("backend", "backend_pid")):
        pid = read_pid(paths[pid_key])
        was_running = is_process_running(pid)
        stopped = stop_pid(pid)
        if was_running and stopped:
            print(f"[stop] {label} 종료 요청 완료 (pid={pid})")
            stopped_any = True
        elif was_running and not stopped:
            print(f"[fail] {label} 종료에 실패했습니다. pid={pid}")
            failed_labels.append(label)
        remove_file(paths[pid_key])

    if not stopped_any:
        print("[stop] 종료할 개발 서버가 없습니다.")
    elif failed_labels:
        print(f"[fail] 종료되지 않은 개발 서버가 있습니다: {', '.join(failed_labels)}")
        return 1
    else:
        print("[done] 개발 서버를 종료했습니다.")
    return 0


def prepare_services_for_launch() -> bool:
    status = read_status()
    backend_running = status["backend"]["running"]
    frontend_running = status["frontend"]["running"]
    stale_backend_pid = status["backend"]["pid"] and not backend_running
    stale_frontend_pid = status["frontend"]["pid"] and not frontend_running

    if backend_running or frontend_running:
        print("[info] 이미 실행 중인 개발 서버를 자동으로 종료한 뒤 다시 시작합니다.")
        print_status()
        if stop_services() != 0:
            print(f"[hint] 필요하면 수동 종료를 시도하세요: {canonical_python_command('start.py', '--stop')}")
            return False
        return True

    if stale_backend_pid or stale_frontend_pid:
        print("[info] 이전 실행의 PID 흔적을 정리한 뒤 다시 시작합니다.")
        stop_services()
    return True


def launch_services() -> int:
    python_command = find_project_python()
    frontend_command = frontend_dev_command()

    if not python_command:
        print("[fail] 프로젝트용 Python 실행기를 찾지 못했습니다. `repo-local venv`, 현재 Python, `py -3` 순서로 확인합니다.")
        return 1

    if not frontend_command:
        print("[fail] 프론트 실행 명령을 만들지 못했습니다. Node.js와 npm 설치를 확인하세요.")
        return 1

    if not prepare_services_for_launch():
        return 1

    backend_dir = ROOT / "backend"
    frontend_dir = ROOT / "frontend"
    paths = runtime_paths()

    backend_stream = None
    frontend_stream = None
    backend_proc: subprocess.Popen[str] | None = None
    frontend_proc: subprocess.Popen[str] | None = None
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0

    try:
        backend_stream = paths["backend_log"].open("w", encoding="utf-8")
        frontend_stream = paths["frontend_log"].open("w", encoding="utf-8")

        print("[start] Stock Predict 개발 서버를 시작합니다.")
        print(f"[start] 로그 위치: {display_path(paths['dir'])}")

        backend_proc = subprocess.Popen(
            [*python_command, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
            cwd=display_path(backend_dir),
            stdout=backend_stream,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        write_pid(paths["backend_pid"], backend_proc.pid)

        print("[start] 백엔드 준비 대기 중...")
        if not wait_for_http(BACKEND_URL, 25, backend_proc.pid, "백엔드", paths["backend_log"]):
            stop_services()
            return 1

        frontend_proc = subprocess.Popen(
            frontend_command,
            cwd=display_path(frontend_dir),
            stdout=frontend_stream,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        write_pid(paths["frontend_pid"], frontend_proc.pid)

        print("[start] 프론트 준비 대기 중...")
        if not wait_for_http(FRONTEND_URL, 45, frontend_proc.pid, "프론트엔드", paths["frontend_log"]):
            stop_services()
            return 1

        print("")
        print("[done] 개발 서버가 백그라운드에서 실행 중입니다.")
        print("Frontend: http://localhost:3000")
        print("Backend:  http://localhost:8000")
        print("API Docs: http://localhost:8000/docs")
        print(f"백엔드 로그: {display_path(paths['backend_log'])}")
        print(f"프론트 로그: {display_path(paths['frontend_log'])}")
        print("현재 프롬프트로 바로 돌아왔다면 정상이며, 같은 터미널에서 다른 명령을 계속 입력해도 됩니다.")
        print("같은 명령을 다시 실행하면 기존 개발 서버를 자동으로 종료한 뒤 재시작합니다.")
        print("")
        print(f"기준 명령: {canonical_python_command('start.py')}")
        print("같은 명령 뒤에 `--status`, `--stop`, `--check` 옵션만 붙여 재사용하면 됩니다.")
        return 0
    finally:
        if frontend_stream is not None:
            frontend_stream.close()
        if backend_stream is not None:
            backend_stream.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock Predict 개발 서버 런처")
    parser.add_argument("--check", action="store_true", help="개발 서버 시작 전에 환경만 점검합니다.")
    parser.add_argument("--status", action="store_true", help="현재 개발 서버 상태를 확인합니다.")
    parser.add_argument("--stop", action="store_true", help="실행 중인 개발 서버를 종료합니다.")
    parser.add_argument("--skip-frontend", action="store_true", help="--check에서 프론트 실행기 점검을 건너뜁니다.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.check:
        return run_check(skip_frontend=args.skip_frontend)
    if args.status:
        return print_status()
    if args.stop:
        return stop_services()
    return launch_services()


if __name__ == "__main__":
    raise SystemExit(main())
