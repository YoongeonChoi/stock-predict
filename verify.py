from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse
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
    parser.add_argument("--deployed-site-smoke", action="store_true", help="운영 Vercel/Render URL을 직접 호출해 배포 상태를 점검합니다.")
    parser.add_argument("--browser-smoke", action="store_true", help="실제 브라우저 기준으로 주요 first usable 화면을 점검합니다.")
    parser.add_argument("--browser-smoke-url", default="", help="브라우저 smoke 대상 URL. 기본값은 로컬 http://127.0.0.1:3000 입니다.")
    return parser.parse_args(argv)


def is_local_browser_target(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost"}


def warm_browser_routes(base_url: str) -> None:
    targets = (
        "/",
        "/radar",
        "/portfolio",
        "/watchlist",
        "/settings",
        "/stock/003670.KS",
    )
    for path in targets:
        url = base_url.rstrip("/") + path
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    if 200 <= response.status < 500:
                        break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(attempt)


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

    browser_smoke_url = args.browser_smoke_url or "http://127.0.0.1:3000"
    should_run_browser_smoke = args.browser_smoke or args.deployed_site_smoke
    if should_run_browser_smoke and is_local_browser_target(browser_smoke_url):
        run_step("Launch local dev server", [python_path, str(ROOT / "start.py")], ROOT)
        run_step(
            "Warm browser routes",
            [python_path, "-c", f"from verify import warm_browser_routes; warm_browser_routes('{browser_smoke_url}')"],
            ROOT,
        )

    if args.browser_smoke:
        run_step(
            "Browser smoke",
            [
                python_path,
                str(ROOT / "scripts" / "browser_smoke.py"),
                "--base-url",
                browser_smoke_url,
                "--attempts",
                "6",
                "--retry-delay",
                "2.5",
                "--virtual-time-budget-ms",
                "18000",
            ],
            ROOT,
        )

    if args.deployed_site_smoke:
        run_step("Deployed site smoke", [python_path, str(ROOT / "scripts" / "deployed_site_smoke.py")], ROOT)
        deployed_frontend_url = "https://www.yoongeon.xyz"
        run_step(
            "Deployed browser smoke",
            [
                python_path,
                str(ROOT / "scripts" / "browser_smoke.py"),
                "--base-url",
                deployed_frontend_url,
                "--attempts",
                "6",
                "--retry-delay",
                "2.5",
                "--virtual-time-budget-ms",
                "18000",
            ],
            ROOT,
        )

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
