from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dev_runtime import (
    ROOT,
    display_command,
    display_path,
    find_project_python,
    frontend_build_command,
    frontend_typecheck_command,
)
from scripts.route_contracts import iter_browser_route_paths


BACKEND_REQUIREMENTS = ROOT / "backend" / "requirements.txt"
BACKEND_IMPORT_NAME_OVERRIDES = {
    "pydantic-settings": "pydantic_settings",
    "python-dotenv": "dotenv",
    "pandas-market-calendars": "pandas_market_calendars",
    "fpdf2": "fpdf",
}
BACKEND_TEST_EXTRA_IMPORTS = ("requests",)
VERIFY_LOCK_PATH = ROOT / ".verify.lock"
VERIFY_LOCK_STALE_SECONDS = 6 * 60 * 60
BROWSER_SMOKE_VIEWPORT_MATRIX_MAX_TOTAL_SECONDS = 600
DEPLOYED_SITE_SMOKE_API_TIMEOUT_SECONDS = 60
DEPLOYED_SITE_SMOKE_FRONTEND_TIMEOUT_SECONDS = 20
DEPLOYED_SITE_SMOKE_ATTEMPTS = 2
DEPLOYED_SITE_SMOKE_RETRY_DELAY_SECONDS = 1.5
DEPLOYED_SITE_SMOKE_MAX_TOTAL_SECONDS = 180


@dataclass(frozen=True)
class VerifyStageSelection:
    run_frontend_checks: bool
    run_live_api_smoke: bool
    run_browser_smoke: bool
    run_deployed_site_smoke: bool
    run_auth_write_smoke: bool


def run_step(label: str, command: list[str], cwd) -> None:
    print(f"[verify] {label}", flush=True)
    print(f"[cmd] {display_command(command)}", flush=True)
    completed = subprocess.run(command, cwd=display_path(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock Predict verification runner")
    parser.add_argument("--full-sweep", action="store_true", help="Run the full ordered regression sweep")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build and typecheck")
    parser.add_argument("--live-api-smoke", action="store_true", help="Run local API smoke checks")
    parser.add_argument("--deployed-site-smoke", action="store_true", help="Run deployed frontend and API smoke checks")
    parser.add_argument("--browser-smoke", action="store_true", help="Run browser first-usable smoke checks")
    parser.add_argument("--browser-smoke-url", default="", help="Override the browser smoke base URL")
    parser.add_argument("--auth-write-smoke", action="store_true", help="Run reversible authenticated write smoke checks")
    parser.add_argument("--allow-parallel", action="store_true", help="Skip the workspace verify lock and allow concurrent runs")
    return parser.parse_args(argv)


def is_local_browser_target(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.hostname in {"127.0.0.1", "localhost"}


def resolve_stage_selection(args: argparse.Namespace) -> VerifyStageSelection:
    return VerifyStageSelection(
        run_frontend_checks=not args.skip_frontend,
        run_live_api_smoke=args.live_api_smoke or args.full_sweep,
        run_browser_smoke=args.browser_smoke or args.full_sweep,
        run_deployed_site_smoke=args.deployed_site_smoke or args.full_sweep,
        run_auth_write_smoke=args.auth_write_smoke or args.full_sweep,
    )


def requirement_to_import_name(line: str) -> str | None:
    cleaned = line.split("#", 1)[0].strip()
    if not cleaned or cleaned.startswith(("-", "--")):
        return None
    package_name = re.split(r"[<>=!~]", cleaned, maxsplit=1)[0].strip()
    package_name = package_name.split("[", 1)[0].strip()
    if not package_name:
        return None
    return BACKEND_IMPORT_NAME_OVERRIDES.get(package_name, package_name.replace("-", "_"))


def load_backend_import_probes() -> tuple[str, ...]:
    modules: list[str] = []
    if BACKEND_REQUIREMENTS.exists():
        for line in BACKEND_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
            import_name = requirement_to_import_name(line)
            if import_name:
                modules.append(import_name)
    modules.extend(BACKEND_TEST_EXTRA_IMPORTS)
    return tuple(dict.fromkeys(modules))


def missing_python_modules(python_command: list[str], modules: tuple[str, ...]) -> list[str]:
    if not modules:
        return []

    probe_script = (
        "import importlib.util\n"
        f"modules = {list(modules)!r}\n"
        "missing = [name for name in modules if importlib.util.find_spec(name) is None]\n"
        "if missing:\n"
        "    print('\\n'.join(missing))\n"
        "raise SystemExit(1 if missing else 0)\n"
    )
    completed = subprocess.run(
        [*python_command, "-c", probe_script],
        cwd=display_path(ROOT / "backend"),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return []
    if completed.returncode != 1:
        detail = completed.stderr.strip() or completed.stdout.strip() or str(completed.returncode)
        raise SystemExit(f"Backend dependency probe failed unexpectedly: {detail}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def ensure_backend_test_dependencies(python_command: list[str]) -> None:
    print("[verify] Backend dependency probe", flush=True)
    missing = missing_python_modules(python_command, load_backend_import_probes())
    if missing:
        missing_list = ", ".join(missing)
        raise SystemExit(
            "Backend test dependencies are missing for the selected Python command: "
            f"{missing_list}. Install {display_path(BACKEND_REQUIREMENTS)} and rerun verify."
        )
    print("[ok] backend requirements import probe passed", flush=True)


def warm_browser_routes(base_url: str) -> None:
    targets = tuple(iter_browser_route_paths())
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


def build_warm_browser_routes_command(python_command: list[str], base_url: str) -> list[str]:
    return [
        *python_command,
        "-c",
        f"from verify import warm_browser_routes; warm_browser_routes('{base_url}')",
    ]


def build_browser_smoke_command(python_command: list[str], base_url: str) -> list[str]:
    return [
        *python_command,
        str(ROOT / "scripts" / "browser_smoke.py"),
        "--base-url",
        base_url,
        "--attempts",
        "6",
        "--retry-delay",
        "2.5",
        "--virtual-time-budget-ms",
        "18000",
        "--command-timeout-seconds",
        "30",
        "--max-total-seconds",
        str(BROWSER_SMOKE_VIEWPORT_MATRIX_MAX_TOTAL_SECONDS),
        "--viewport-matrix",
    ]


def build_deployed_site_smoke_command(python_command: list[str]) -> list[str]:
    return [
        *python_command,
        str(ROOT / "scripts" / "deployed_site_smoke.py"),
        "--api-timeout",
        str(DEPLOYED_SITE_SMOKE_API_TIMEOUT_SECONDS),
        "--frontend-timeout",
        str(DEPLOYED_SITE_SMOKE_FRONTEND_TIMEOUT_SECONDS),
        "--attempts",
        str(DEPLOYED_SITE_SMOKE_ATTEMPTS),
        "--retry-delay",
        str(DEPLOYED_SITE_SMOKE_RETRY_DELAY_SECONDS),
        "--max-total-seconds",
        str(DEPLOYED_SITE_SMOKE_MAX_TOTAL_SECONDS),
        "--fail-fast",
    ]


def _read_lock_metadata(lock_path: Path) -> dict:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _lock_is_stale(lock_path: Path, *, now: float | None = None) -> bool:
    try:
        created_at = lock_path.stat().st_mtime
    except FileNotFoundError:
        return False
    current_time = time.time() if now is None else now
    return (current_time - created_at) > VERIFY_LOCK_STALE_SECONDS


@contextmanager
def acquire_verify_lock(*, enabled: bool = True):
    if not enabled:
        yield
        return

    lock_path = VERIFY_LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if _lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            metadata = _read_lock_metadata(lock_path)
            owner_pid = metadata.get("pid", "unknown")
            started_at = metadata.get("started_at", "unknown")
            raise SystemExit(
                "Another verify.py run appears to be active for this workspace. "
                f"pid={owner_pid}, started_at={started_at}, lock={display_path(lock_path)}. "
                "Wait for it to finish or rerun with --allow-parallel if you really want overlapping runs."
            )

    payload = {
        "pid": os.getpid(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "cwd": display_path(ROOT),
    }
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    stages = resolve_stage_selection(args)
    python_command = find_project_python()
    build_command = frontend_build_command()
    typecheck_command = frontend_typecheck_command()

    if not python_command:
        raise SystemExit(
            "Could not find a usable Python command. "
            "Resolution order is repo-local venv -> current Python -> Windows py -3."
        )
    with acquire_verify_lock(enabled=not args.allow_parallel):
        launcher_check_command = [*python_command, str(ROOT / "start.py"), "--check"]
        if args.skip_frontend:
            launcher_check_command.append("--skip-frontend")
        run_step("Launcher check", launcher_check_command, ROOT)
        run_step("Backend compileall", [*python_command, "-m", "compileall", "app"], ROOT / "backend")
        ensure_backend_test_dependencies(python_command)
        run_step("Backend unittest", [*python_command, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "backend")

        if stages.run_frontend_checks:
            if not build_command:
                raise SystemExit(
                    "Could not resolve the frontend build command. "
                    "Resolution order is frontend/node_modules/.bin -> PATH npm -> standard Windows nodejs install."
                )
            if not typecheck_command:
                raise SystemExit(
                    "Could not resolve the frontend typecheck command. "
                    "Resolution order is frontend/node_modules/.bin -> PATH npx -> standard Windows nodejs install."
                )
            run_step("Frontend build", build_command, ROOT / "frontend")
            run_step("Frontend typecheck", typecheck_command, ROOT / "frontend")

        browser_smoke_url = args.browser_smoke_url or "http://127.0.0.1:3000"
        if stages.run_browser_smoke and is_local_browser_target(browser_smoke_url):
            run_step("Launch local dev server", [*python_command, str(ROOT / "start.py")], ROOT)
            run_step("Warm browser routes", build_warm_browser_routes_command(python_command, browser_smoke_url), ROOT)

        if stages.run_browser_smoke:
            run_step("Browser smoke", build_browser_smoke_command(python_command, browser_smoke_url), ROOT)

        if stages.run_live_api_smoke:
            run_step("Backend live API smoke", [*python_command, "scripts/live_api_smoke.py"], ROOT / "backend")

        if stages.run_deployed_site_smoke:
            run_step(
                "Deployed site smoke",
                build_deployed_site_smoke_command(python_command),
                ROOT,
            )
            deployed_frontend_url = "https://www.yoongeon.xyz"
            run_step(
                "Warm deployed browser routes",
                build_warm_browser_routes_command(python_command, deployed_frontend_url),
                ROOT,
            )
            run_step(
                "Deployed browser smoke",
                build_browser_smoke_command(python_command, deployed_frontend_url),
                ROOT,
            )

        if stages.run_auth_write_smoke:
            run_step(
                "Reversible auth write smoke",
                [*python_command, str(ROOT / "scripts" / "reversible_auth_smoke.py")],
                ROOT,
            )

    print("[done] verification complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
