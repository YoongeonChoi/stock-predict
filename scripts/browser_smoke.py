from __future__ import annotations

import argparse
<<<<<<< HEAD
import html
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
=======
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from route_contracts import DEFAULT_FORBIDDEN_TEXTS, iter_browser_route_contracts
>>>>>>> main


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "browser-smoke"
<<<<<<< HEAD
COMMON_FORBIDDEN = (
    "Failed to fetch",
    "32초 안에 응답이 오지 않았습니다.",
)
NETWORK_ERROR_MARKERS = (
    "원격 서버에 연결할 수 없습니다.",
    "사이트에 연결할 수 없음",
    "ERR_CONNECTION_REFUSED",
    "ERR_CONNECTION_TIMED_OUT",
)
=======
DEFAULT_LOCAL_BASE = "http://127.0.0.1:3000"
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30.0
NETWORK_ERROR_MARKERS = (
    "ERR_CONNECTION_REFUSED",
    "ERR_CONNECTION_TIMED_OUT",
    "This site can’t be reached",
    "This site can't be reached",
)
DEFAULT_BROWSER_CANDIDATES = (
    os.getenv("EDGE_PATH", ""),
    os.getenv("CHROME_PATH", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
DEFAULT_VIEWPORT = "1600x1200"
RESPONSIVE_VIEWPORTS = ("360x800", "390x844", "768x1024", "1024x768", "1440x900")
>>>>>>> main


@dataclass(frozen=True)
class BrowserCheck:
    name: str
    path: str
<<<<<<< HEAD
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    min_text_length: int = 80


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실브라우저 기준 hydration 후 주요 화면 smoke 점검")
    parser.add_argument(
        "--base-url",
        default=os.getenv("STOCK_PREDICT_BROWSER_SMOKE_URL", ""),
        help="점검할 프론트엔드 기본 URL. 지정하지 않으면 운영 URL 또는 로컬 127.0.0.1:3000을 사용합니다.",
    )
    parser.add_argument(
        "--virtual-time-budget-ms",
        type=int,
        default=45000,
        help="브라우저가 hydration과 비동기 fetch를 기다리는 가상 시간 예산(ms)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="각 페이지 점검 프로세스 timeout(초)",
    )
    return parser.parse_args(argv)


def resolve_base_url(value: str) -> str:
    base = value.strip() or os.getenv("STOCK_PREDICT_FRONTEND_URL", "").strip()
    if not base:
        base = "http://127.0.0.1:3000"
    parsed = urlsplit(base)
    if parsed.hostname == "localhost":
        netloc = parsed.netloc.replace("localhost", "127.0.0.1", 1)
        base = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    return base.rstrip("/")


def resolve_browser_executable() -> str:
    explicit = os.getenv("STOCK_PREDICT_BROWSER_EXECUTABLE", "").strip()
    if explicit and Path(explicit).exists():
        return explicit

    candidates = [
        shutil.which("msedge.exe"),
        shutil.which("chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise RuntimeError(
        "headless browser executable을 찾지 못했습니다. STOCK_PREDICT_BROWSER_EXECUTABLE 환경변수를 지정하거나 Edge/Chrome을 설치해 주세요."
    )


def sanitize_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "route"


def to_plain_text(html_text: str) -> str:
    compact = re.sub(r"<script\\b[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    compact = re.sub(r"<style\\b[^>]*>.*?</style>", " ", compact, flags=re.IGNORECASE | re.DOTALL)
    compact = re.sub(r"<[^>]+>", " ", compact)
    compact = html.unescape(compact)
    compact = re.sub(r"\s+", " ", compact)
    return compact.strip()


def is_browser_error_page(dom: str, text: str, url: str) -> bool:
    parsed = urlsplit(url)
    title_match = re.search(r"<title>([^<]+)</title>", dom, flags=re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""
    if any(marker in text or marker in dom for marker in NETWORK_ERROR_MARKERS):
        return True
    return bool(parsed.hostname and title and title == parsed.hostname)


def dump_dom(executable: str, url: str, *, virtual_time_budget_ms: int, timeout_seconds: int) -> tuple[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = OUTPUT_DIR / f"{sanitize_name(url)}.png"
    command = [
        executable,
        "--headless=new",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--hide-scrollbars",
        "--mute-audio",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1440,2200",
        f"--virtual-time-budget={virtual_time_budget_ms}",
        f"--screenshot={screenshot_path}",
        "--dump-dom",
        url,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(stderr or f"headless browser exited with code {completed.returncode}")
    return completed.stdout, str(screenshot_path)
=======
    required_texts: tuple[str, ...] = ()
    any_of_texts: tuple[str, ...] = ()
    forbidden_texts: tuple[str, ...] = DEFAULT_FORBIDDEN_TEXTS


CHECKS = tuple(
    BrowserCheck(
        name=contract.key,
        path=contract.route,
        required_texts=contract.smoke.required_texts or contract.required_visible_state,
        any_of_texts=contract.smoke.any_of_texts or contract.optional_upgrade_state,
        forbidden_texts=contract.smoke.forbidden_texts or DEFAULT_FORBIDDEN_TEXTS,
    )
    for contract in iter_browser_route_contracts()
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser first-usable smoke")
    parser.add_argument("--base-url", default=DEFAULT_LOCAL_BASE, help="Base URL for browser smoke")
    parser.add_argument("--browser", default="", help="Path to Edge or Chrome executable")
    parser.add_argument("--attempts", type=int, default=5, help="Attempts per route")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Retry delay in seconds")
    parser.add_argument("--virtual-time-budget-ms", type=int, default=12000, help="Headless browser virtual time budget")
    parser.add_argument(
        "--command-timeout-seconds",
        type=float,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
        help="Per-browser subprocess timeout in seconds",
    )
    parser.add_argument(
        "--max-total-seconds",
        type=float,
        default=0.0,
        help="Fail the whole browser smoke after this many seconds; 0 disables the limit",
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Directory for HTML and screenshots")
    parser.add_argument("--viewport", action="append", default=[], help="Viewport in WIDTHxHEIGHT form. Repeat to test multiple.")
    parser.add_argument("--viewport-matrix", action="store_true", help="Run the canonical responsive viewport matrix")
    return parser.parse_args(argv)


def normalize_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    if parsed.hostname == "localhost":
        netloc = parsed.netloc.replace("localhost", "127.0.0.1", 1)
        parsed = parsed._replace(netloc=netloc)
    return urlunparse(parsed)


def resolve_browser(candidate: str) -> str:
    if candidate:
        path = Path(candidate)
        if path.exists():
            return str(path)
        raise SystemExit(f"Browser executable not found: {candidate}")

    for raw in DEFAULT_BROWSER_CANDIDATES:
        if not raw:
            continue
        path = Path(raw)
        if path.exists():
            return str(path)

    raise SystemExit("Could not find an Edge or Chrome executable. Pass --browser explicitly.")


def sanitize_name(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", url).strip("-")


def parse_viewport(raw: str) -> tuple[int, int]:
    match = re.fullmatch(r"(?P<width>\d{2,5})x(?P<height>\d{2,5})", raw.strip())
    if not match:
        raise SystemExit(f"Invalid viewport '{raw}'. Expected WIDTHxHEIGHT, for example 390x844.")
    width = int(match.group("width"))
    height = int(match.group("height"))
    if width < 200 or height < 200:
        raise SystemExit(f"Viewport '{raw}' is too small for browser smoke.")
    return width, height


def resolve_viewports(args: argparse.Namespace) -> tuple[tuple[int, int], ...]:
    raw_viewports = list(args.viewport or [])
    if args.viewport_matrix:
        raw_viewports.extend(RESPONSIVE_VIEWPORTS)
    if not raw_viewports:
        raw_viewports = [DEFAULT_VIEWPORT]
    return tuple(dict.fromkeys(parse_viewport(viewport) for viewport in raw_viewports))


def decode_browser_output(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def resolve_command_timeout_seconds(virtual_time_budget_ms: int, requested_timeout_seconds: float) -> float:
    minimum_timeout = max((virtual_time_budget_ms / 1000.0) + 10.0, 12.0)
    return max(float(requested_timeout_seconds), minimum_timeout)


def remaining_timeout_seconds(command_timeout_seconds: float, deadline_monotonic: float | None) -> float | None:
    if deadline_monotonic is None:
        return command_timeout_seconds
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        return None
    return max(min(command_timeout_seconds, remaining), 1.0)


def dump_dom(
    browser: str,
    url: str,
    virtual_time_budget_ms: int,
    viewport: tuple[int, int],
    *,
    command_timeout_seconds: float,
) -> str:
    with tempfile.TemporaryDirectory(prefix="stock-predict-browser-smoke-") as temp_dir:
        width, height = viewport
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            f"--window-size={width},{height}",
            f"--user-data-dir={temp_dir}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
            "--dump-dom",
            url,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=command_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"browser dump-dom timed out after {float(exc.timeout):.1f}s") from exc
        if completed.returncode != 0:
            stderr = " ".join(decode_browser_output(completed.stderr).split())
            raise RuntimeError(f"browser dump-dom failed: {stderr or completed.returncode}")
        return decode_browser_output(completed.stdout)


def save_screenshot(
    browser: str,
    url: str,
    destination: Path,
    virtual_time_budget_ms: int,
    viewport: tuple[int, int],
    *,
    command_timeout_seconds: float,
) -> None:
    with tempfile.TemporaryDirectory(prefix="stock-predict-browser-shot-") as temp_dir:
        width, height = viewport
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            f"--window-size={width},{height}",
            f"--user-data-dir={temp_dir}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
            f"--screenshot={destination}",
            url,
        ]
        try:
            subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=command_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return


def collapse_text(html: str) -> str:
    return " ".join(html.split())


def is_browser_error_page(dom: str, text: str) -> bool:
    if "<title>127.0.0.1</title>" in dom:
        return True
    return any(marker in text for marker in NETWORK_ERROR_MARKERS)


def evaluate_check(check: BrowserCheck, html: str) -> tuple[bool, str]:
    text = collapse_text(html)
    if is_browser_error_page(html, text):
        return False, "browser error page"

    forbidden_hits = [marker for marker in check.forbidden_texts if marker in text]
    if forbidden_hits:
        return False, f"forbidden text {forbidden_hits}"

    missing = [needle for needle in check.required_texts if needle not in text]
    if missing:
        return False, f"missing required text {missing}"

    if check.any_of_texts and not any(needle in text for needle in check.any_of_texts):
        return False, f"missing any-of texts {check.any_of_texts}"

    return True, "ok"


def run_check(
    browser: str,
    base_url: str,
    check: BrowserCheck,
    attempts: int,
    retry_delay: float,
    virtual_time_budget_ms: int,
    output_dir: Path,
    viewport: tuple[int, int],
    command_timeout_seconds: float,
    deadline_monotonic: float | None = None,
) -> tuple[bool, str]:
    url = urljoin(base_url.rstrip("/") + "/", check.path.lstrip("/"))
    viewport_name = f"{viewport[0]}x{viewport[1]}"
    html_path = output_dir / f"{sanitize_name(url)}-{viewport_name}.html"
    screenshot_path = output_dir / f"{sanitize_name(url)}-{viewport_name}.png"

    last_reason = "unknown failure"
    last_html = ""

    for attempt in range(1, attempts + 1):
        timeout_seconds = remaining_timeout_seconds(command_timeout_seconds, deadline_monotonic)
        if timeout_seconds is None:
            last_reason = "browser smoke deadline exceeded"
            break
        try:
            html = dump_dom(
                browser,
                url,
                virtual_time_budget_ms,
                viewport,
                command_timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            last_reason = str(exc)
            html = ""
        else:
            success, reason = evaluate_check(check, html)
            last_reason = reason
            last_html = html
            if success:
                html_path.write_text(html, encoding="utf-8")
                save_screenshot(
                    browser,
                    url,
                    screenshot_path,
                    virtual_time_budget_ms,
                    viewport,
                    command_timeout_seconds=timeout_seconds,
                )
                return True, f"{viewport_name} screenshot {screenshot_path}"

        if attempt < attempts:
            time.sleep(retry_delay * attempt)

    if last_html:
        html_path.write_text(last_html, encoding="utf-8")
    timeout_seconds = remaining_timeout_seconds(command_timeout_seconds, deadline_monotonic)
    if timeout_seconds is not None:
        save_screenshot(
            browser,
            url,
            screenshot_path,
            virtual_time_budget_ms,
            viewport,
            command_timeout_seconds=timeout_seconds,
        )
    return False, last_reason
>>>>>>> main


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
<<<<<<< HEAD
    base_url = resolve_base_url(args.base_url)
    executable = resolve_browser_executable()

    checks = [
        BrowserCheck(
            name="home",
            path="/",
            all_of=("대시보드",),
            any_of=("오늘의 포커스", "시장 히트맵", "강한 셋업", "주요 뉴스"),
            forbidden=COMMON_FORBIDDEN,
            min_text_length=140,
        ),
        BrowserCheck(
            name="radar",
            path="/radar",
            all_of=("기회 레이더",),
            any_of=("첫 판단 스레드", "KR 시장 국면", "표시 후보"),
            forbidden=COMMON_FORBIDDEN + ("기회 레이더를 아직 불러오지 못했습니다",),
            min_text_length=140,
        ),
        BrowserCheck(
            name="stock",
            path="/stock/003670.KS",
            any_of=("003670", "판단 요약", "신뢰 메모", "현재가"),
            forbidden=COMMON_FORBIDDEN + ("연결이 지연되고 있습니다", "서버 연결이 아직 준비되지 않았습니다."),
            min_text_length=140,
        ),
        BrowserCheck(
            name="portfolio",
            path="/portfolio",
            all_of=("포트폴리오",),
            any_of=("공개 레이더 기반 포트폴리오 미리보기", "총자산 설정", "자산 구성"),
            forbidden=COMMON_FORBIDDEN + ("계정 자산 워크스페이스를 아직 불러오지 못했습니다",),
            min_text_length=120,
        ),
        BrowserCheck(
            name="watchlist",
            path="/watchlist",
            all_of=("관심종목",),
            any_of=("공개 레이더 기반 미리보기", "현재 상태", "저장된 관심종목"),
            forbidden=COMMON_FORBIDDEN + ("관심종목을 불러오지 못했습니다",),
            min_text_length=120,
        ),
        BrowserCheck(
            name="settings",
            path="/settings",
            any_of=("설정 및 시스템", "로그인", "이메일로 로그인"),
            forbidden=COMMON_FORBIDDEN,
            min_text_length=80,
        ),
    ]

    failures: list[str] = []

    print(f"[browser-smoke] browser={executable}")
    print(f"[browser-smoke] base={base_url}")

    for check in checks:
        url = urljoin(f"{base_url}/", check.path.lstrip("/"))
        try:
            dom, screenshot_path = dump_dom(
                executable,
                url,
                virtual_time_budget_ms=args.virtual_time_budget_ms,
                timeout_seconds=args.timeout_seconds,
            )
        except Exception as exc:
            failures.append(f"{check.name}: {exc}")
            print(f"[FAIL] {check.name:12} {url} -> {exc}")
            continue

        dom_path = OUTPUT_DIR / f"{check.name}.html"
        dom_path.write_text(dom, encoding="utf-8")
        text = to_plain_text(dom)

        if is_browser_error_page(dom, text, url):
            failures.append(f"{check.name}: browser network error page")
            print(f"[FAIL] {check.name:12} {url} -> browser network error page")
            continue

        if len(text) < check.min_text_length:
            failures.append(f"{check.name}: visible text too short ({len(text)})")
            print(f"[FAIL] {check.name:12} {url} -> visible text too short ({len(text)})")
            continue

        missing_all = [token for token in check.all_of if token not in text]
        if missing_all:
            failures.append(f"{check.name}: missing required text {missing_all!r}")
            print(f"[FAIL] {check.name:12} {url} -> missing required text {missing_all!r}")
            continue

        if check.any_of and not any(token in text for token in check.any_of):
            failures.append(f"{check.name}: missing any-of texts {check.any_of!r}")
            print(f"[FAIL] {check.name:12} {url} -> missing any-of texts {check.any_of!r}")
            continue

        forbidden_hit = next((token for token in check.forbidden if token in text or token in dom), None)
        if forbidden_hit:
            failures.append(f"{check.name}: forbidden text {forbidden_hit!r}")
            print(f"[FAIL] {check.name:12} {url} -> forbidden text {forbidden_hit!r}")
            continue

        print(f"[OK]   {check.name:12} {url} -> screenshot {screenshot_path}")

    if failures:
        print("\n[browser-smoke] 실패 항목:")
=======
    browser = resolve_browser(args.browser)
    base_url = normalize_base_url(args.base_url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    viewports = resolve_viewports(args)
    command_timeout_seconds = resolve_command_timeout_seconds(
        max(args.virtual_time_budget_ms, 2000),
        max(args.command_timeout_seconds, 1.0),
    )
    deadline_monotonic = None
    if args.max_total_seconds > 0:
        deadline_monotonic = time.monotonic() + args.max_total_seconds

    print(f"[browser-smoke] browser={browser}")
    print(f"[browser-smoke] base={base_url}")
    print("[browser-smoke] viewports=" + ", ".join(f"{width}x{height}" for width, height in viewports))
    print(f"[browser-smoke] command-timeout={command_timeout_seconds:.1f}s")
    if deadline_monotonic is not None:
        print(f"[browser-smoke] max-total-seconds={args.max_total_seconds:.1f}s")

    failures: list[str] = []

    for viewport in viewports:
        viewport_label = f"{viewport[0]}x{viewport[1]}"
        for check in CHECKS:
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                failures.append(f"global: exceeded {args.max_total_seconds:.1f}s total browser smoke budget")
                print(f"[FAIL] browser-smoke global deadline exceeded after {args.max_total_seconds:.1f}s")
                break
            ok, detail = run_check(
                browser=browser,
                base_url=base_url,
                check=check,
                attempts=max(args.attempts, 1),
                retry_delay=max(args.retry_delay, 0.5),
                virtual_time_budget_ms=max(args.virtual_time_budget_ms, 2000),
                output_dir=output_dir,
                viewport=viewport,
                command_timeout_seconds=command_timeout_seconds,
                deadline_monotonic=deadline_monotonic,
            )
            url = urljoin(base_url.rstrip("/") + "/", check.path.lstrip("/"))
            if ok:
                print(f"[OK]   {check.name:12} [{viewport_label}] {url} -> {detail}")
            else:
                failures.append(f"{check.name}[{viewport_label}]: {detail}")
                print(f"[FAIL] {check.name:12} [{viewport_label}] {url} -> {detail}")
        if failures and failures[-1].startswith("global: exceeded"):
            break

    if failures:
        print("\n[browser-smoke] failures detected:")
>>>>>>> main
        for failure in failures:
            print(f"- {failure}")
        return 1

<<<<<<< HEAD
    print("\n[browser-smoke] 모든 hydration 후 화면 점검 통과")
=======
    print("\n[browser-smoke] all checks passed")
>>>>>>> main
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
