from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "browser-smoke"
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


@dataclass(frozen=True)
class BrowserCheck:
    name: str
    path: str
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[browser-smoke] 모든 hydration 후 화면 점검 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
