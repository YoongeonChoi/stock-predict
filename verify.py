from __future__ import annotations

import argparse
import subprocess
import sys
from dev_runtime import (
    ROOT,
    display_path,
    find_project_python,
    frontend_build_command,
    frontend_typecheck_command,
)


def run_step(label: str, command: list[str], cwd) -> None:
    print(f"[verify] {label}", flush=True)
    completed = subprocess.run(command, cwd=display_path(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock Predict 검증 런처")
    parser.add_argument("--skip-frontend", action="store_true", help="프론트 검증을 건너뜁니다.")
    parser.add_argument("--live-api-smoke", action="store_true", help="주요 API를 실호출 기준으로 점검합니다.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    python_path = find_project_python()
    build_command = frontend_build_command()
    typecheck_command = frontend_typecheck_command()

    if not python_path:
        raise SystemExit("가상환경 Python을 찾을 수 없습니다.")

    run_step("Launcher check", [python_path, str(ROOT / "start.py"), "--check"], ROOT)
    run_step("Backend compileall", [python_path, "-m", "compileall", "app"], ROOT / "backend")
    run_step("Backend unittest", [python_path, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "backend")

    if args.live_api_smoke:
        run_step("Backend live API smoke", [python_path, "scripts/live_api_smoke.py"], ROOT / "backend")

    if not args.skip_frontend:
        if not build_command:
            raise SystemExit("프론트 build 명령을 만들 수 없습니다.")
        if not typecheck_command:
            raise SystemExit("프론트 typecheck 명령을 만들 수 없습니다.")
        run_step("Frontend build", build_command, ROOT / "frontend")
        run_step("Frontend typecheck", typecheck_command, ROOT / "frontend")

    print("[done] 검증 완료", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
