from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "browser-smoke"
DEFAULT_LOCAL_BASE = "http://127.0.0.1:3000"
NETWORK_ERROR_MARKERS = (
    "원격 서버에 연결할 수 없습니다.",
    "사이트에 연결할 수 없음",
    "ERR_CONNECTION_REFUSED",
    "ERR_CONNECTION_TIMED_OUT",
)
FORBIDDEN_TEXT_MARKERS = (
    "Failed to fetch",
    "32초 안에 응답이 오지 않았습니다.",
)
DEFAULT_BROWSER_CANDIDATES = (
    os.getenv("EDGE_PATH", ""),
    os.getenv("CHROME_PATH", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


@dataclass(frozen=True)
class BrowserCheck:
    name: str
    path: str
    required_texts: tuple[str, ...] = ()
    any_of_texts: tuple[str, ...] = ()


CHECKS = (
    BrowserCheck("home", "/", required_texts=("대시보드",)),
    BrowserCheck("radar", "/radar", required_texts=("기회 레이더",)),
    BrowserCheck("stock", "/stock/003670.KS", any_of_texts=("PearlAbyss", "판단 요약", "일부 데이터가 제한적으로 제공됩니다")),
    BrowserCheck("portfolio", "/portfolio", required_texts=("포트폴리오",)),
    BrowserCheck("watchlist", "/watchlist", required_texts=("관심종목",)),
    BrowserCheck("settings", "/settings", any_of_texts=("설정 및 시스템", "로그인", "이메일로 로그인")),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="브라우저 기준 first usable smoke 점검")
    parser.add_argument("--base-url", default=DEFAULT_LOCAL_BASE, help="점검할 프론트 기본 URL")
    parser.add_argument("--browser", default="", help="사용할 브라우저 실행 파일 경로")
    parser.add_argument("--attempts", type=int, default=5, help="각 route 재시도 횟수")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="재시도 간격(초)")
    parser.add_argument("--virtual-time-budget-ms", type=int, default=12000, help="브라우저 가상 시간 예산(ms)")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="HTML/스크린샷 저장 위치")
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
        raise SystemExit(f"브라우저 실행 파일을 찾을 수 없습니다: {candidate}")

    for raw in DEFAULT_BROWSER_CANDIDATES:
        if not raw:
            continue
        path = Path(raw)
        if path.exists():
            return str(path)

    raise SystemExit("Edge 또는 Chrome 실행 파일을 찾을 수 없습니다. --browser 옵션으로 직접 지정해 주세요.")


def sanitize_name(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", url).strip("-")


def dump_dom(browser: str, url: str, virtual_time_budget_ms: int) -> str:
    with tempfile.TemporaryDirectory(prefix="stock-predict-browser-smoke-") as temp_dir:
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--window-size=1600,1200",
            f"--user-data-dir={temp_dir}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
            "--dump-dom",
            url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = " ".join(completed.stderr.split())
            raise RuntimeError(f"browser dump-dom failed: {stderr or completed.returncode}")
        return completed.stdout


def save_screenshot(browser: str, url: str, destination: Path, virtual_time_budget_ms: int) -> None:
    with tempfile.TemporaryDirectory(prefix="stock-predict-browser-shot-") as temp_dir:
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--window-size=1600,1200",
            f"--user-data-dir={temp_dir}",
            f"--virtual-time-budget={virtual_time_budget_ms}",
            f"--screenshot={destination}",
            url,
        ]
        subprocess.run(command, capture_output=True, text=True, check=False)


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

    forbidden_hits = [marker for marker in FORBIDDEN_TEXT_MARKERS if marker in text]
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
) -> tuple[bool, str]:
    url = urljoin(base_url.rstrip("/") + "/", check.path.lstrip("/"))
    html_path = output_dir / f"{sanitize_name(url)}.html"
    screenshot_path = output_dir / f"{sanitize_name(url)}.png"

    last_reason = "unknown failure"
    last_html = ""

    for attempt in range(1, attempts + 1):
        try:
            html = dump_dom(browser, url, virtual_time_budget_ms)
        except Exception as exc:
            last_reason = str(exc)
            html = ""
        else:
            success, reason = evaluate_check(check, html)
            last_reason = reason
            last_html = html
            if success:
                html_path.write_text(html, encoding="utf-8")
                save_screenshot(browser, url, screenshot_path, virtual_time_budget_ms)
                return True, f"screenshot {screenshot_path}"

        if attempt < attempts:
            time.sleep(retry_delay * attempt)

    if last_html:
        html_path.write_text(last_html, encoding="utf-8")
    save_screenshot(browser, url, screenshot_path, virtual_time_budget_ms)
    return False, last_reason


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    browser = resolve_browser(args.browser)
    base_url = normalize_base_url(args.base_url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[browser-smoke] browser={browser}")
    print(f"[browser-smoke] base={base_url}")

    failures: list[str] = []

    for check in CHECKS:
        ok, detail = run_check(
            browser=browser,
            base_url=base_url,
            check=check,
            attempts=max(args.attempts, 1),
            retry_delay=max(args.retry_delay, 0.5),
            virtual_time_budget_ms=max(args.virtual_time_budget_ms, 2000),
            output_dir=output_dir,
        )
        url = urljoin(base_url.rstrip("/") + "/", check.path.lstrip("/"))
        if ok:
            print(f"[OK]   {check.name:12} {url} -> {detail}")
        else:
            failures.append(f"{check.name}: {detail}")
            print(f"[FAIL] {check.name:12} {url} -> {detail}")

    if failures:
        print("\n[browser-smoke] 실패 항목:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[browser-smoke] 모든 브라우저 점검 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
