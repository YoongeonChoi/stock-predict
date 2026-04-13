from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "stock-predict-latency-probe/1.0"


@dataclass(slots=True)
class ProbeRun:
    status_code: int | None
    elapsed_seconds: float
    server: str
    cache_state: str
    render_routing: str
    error: str


@dataclass(slots=True)
class ProbeCase:
    name: str
    url: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="운영 프론트/API 지연 구간 측정")
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("STOCK_PREDICT_FRONTEND_URL", "https://www.yoongeon.xyz"),
        help="운영 프론트 기본 URL",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("STOCK_PREDICT_API_URL", "https://api.yoongeon.xyz"),
        help="운영 API 기본 URL",
    )
    parser.add_argument("--repeats", type=int, default=3, help="각 엔드포인트 반복 횟수")
    parser.add_argument("--timeout-seconds", type=int, default=35, help="각 요청 타임아웃(초)")
    parser.add_argument(
        "--stock-tickers",
        default="003670,005930,000660,035420",
        help="종목 상세 지연 확인용 티커 목록(쉼표 구분)",
    )
    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="/api/diagnostics 요약은 건너뜁니다.",
    )
    return parser.parse_args(argv)


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _fetch(url: str, *, timeout_seconds: int) -> tuple[int, dict[str, str], bytes]:
    request = Request(
        url,
        headers={
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        headers = {str(key).lower(): value for key, value in response.headers.items()}
        return response.getcode(), headers, response.read()


def _measure_case(case: ProbeCase, *, repeats: int, timeout_seconds: int) -> list[ProbeRun]:
    runs: list[ProbeRun] = []
    for _ in range(max(repeats, 1)):
        started_at = time.perf_counter()
        status_code: int | None = None
        server = ""
        cache_state = ""
        render_routing = ""
        error = ""
        try:
            status_code, headers, _ = _fetch(case.url, timeout_seconds=timeout_seconds)
            server = headers.get("server", "")
            cache_state = headers.get("x-vercel-cache") or headers.get("cf-cache-status") or ""
            render_routing = headers.get("x-render-routing", "")
        except HTTPError as exc:
            status_code = exc.code
            headers = {str(key).lower(): value for key, value in exc.headers.items()}
            server = headers.get("server", "")
            cache_state = headers.get("x-vercel-cache") or headers.get("cf-cache-status") or ""
            render_routing = headers.get("x-render-routing", "")
            error = f"HTTPError {exc.code}"
            exc.read()
        except URLError as exc:
            error = f"URLError {exc.reason}"
        except Exception as exc:  # pragma: no cover - defensive for live probe
            error = f"{type(exc).__name__}: {exc}"
        elapsed_seconds = time.perf_counter() - started_at
        runs.append(
            ProbeRun(
                status_code=status_code,
                elapsed_seconds=elapsed_seconds,
                server=server,
                cache_state=cache_state,
                render_routing=render_routing,
                error=error,
            )
        )
    return runs


def _format_float(value: float) -> str:
    return f"{value:.2f}s"


def _print_case(case: ProbeCase, runs: list[ProbeRun]) -> None:
    print(f"=== {case.name} ===")
    for index, run in enumerate(runs, start=1):
        status_display = run.status_code if run.status_code is not None else "-"
        extra_bits = []
        if run.server:
            extra_bits.append(f"server={run.server}")
        if run.cache_state:
            extra_bits.append(f"cache={run.cache_state}")
        if run.render_routing:
            extra_bits.append(f"routing={run.render_routing}")
        if run.error:
            extra_bits.append(f"error={run.error}")
        extras = " ".join(extra_bits) if extra_bits else "-"
        print(
            f"run={index} status={status_display} total={_format_float(run.elapsed_seconds)} {extras}"
        )
    elapsed = [run.elapsed_seconds for run in runs]
    status_counts: dict[str, int] = {}
    for run in runs:
        key = str(run.status_code) if run.status_code is not None else "ERR"
        status_counts[key] = status_counts.get(key, 0) + 1
    print(
        "summary "
        f"median={_format_float(statistics.median(elapsed))} "
        f"min={_format_float(min(elapsed))} "
        f"max={_format_float(max(elapsed))} "
        f"statuses={status_counts}"
    )
    print()


def _load_json(url: str, *, timeout_seconds: int) -> dict[str, Any]:
    status_code, _, body = _fetch(url, timeout_seconds=timeout_seconds)
    if status_code < 200 or status_code >= 300:
        raise RuntimeError(f"{url} returned HTTP {status_code}")
    return json.loads(body.decode("utf-8", errors="replace"))


def _print_diagnostics(api_base_url: str, *, timeout_seconds: int) -> None:
    diagnostics_url = f"{api_base_url}/api/diagnostics"
    payload = _load_json(diagnostics_url, timeout_seconds=timeout_seconds)
    route_rows = payload.get("route_stability_summary") or []
    interesting_routes = {"daily_briefing", "market_opportunities", "stock_detail", "country_report"}
    print("=== diagnostics.route_stability_summary ===")
    printed = 0
    for row in route_rows:
        route = str(row.get("route") or "")
        if route not in interesting_routes:
            continue
        printed += 1
        print(
            f"route={route} total={row.get('total')} "
            f"p50={row.get('p50_elapsed_ms')}ms "
            f"p95={row.get('p95_elapsed_ms')}ms "
            f"fallback_rate={row.get('fallback_served_rate')} "
            f"partial_rate={row.get('partial_rate')} "
            f"cold_start_rate={row.get('cold_start_suspected_rate')} "
            f"cache_mix={row.get('cache_state_mix')}"
        )
    if not printed:
        print("interesting route summary not found")
    print()

    first_usable = payload.get("first_usable_metrics") or {}
    print("=== diagnostics.first_usable_metrics ===")
    print(json.dumps(first_usable, ensure_ascii=False, indent=2))
    print()

    failure_summary = payload.get("failure_class_summary") or {}
    print("=== diagnostics.failure_class_summary ===")
    print(json.dumps(failure_summary, ensure_ascii=False, indent=2))
    print()

    memory_diagnostics = payload.get("memory_diagnostics") or {}
    print("=== diagnostics.memory_diagnostics ===")
    print(json.dumps(memory_diagnostics, ensure_ascii=False, indent=2))
    print()


def build_probe_cases(frontend_url: str, api_url: str, stock_tickers: list[str]) -> list[ProbeCase]:
    stock_html_cases = [
        ProbeCase(name=f"frontend_stock_{ticker}", url=f"{frontend_url}/stock/{ticker}")
        for ticker in stock_tickers
    ]
    stock_api_cases = [
        ProbeCase(name=f"api_stock_detail_{ticker}", url=f"{api_url}/api/stock/{ticker}/detail")
        for ticker in stock_tickers
    ]

    return [
        ProbeCase(name="frontend_home", url=f"{frontend_url}/"),
        ProbeCase(name="frontend_radar", url=f"{frontend_url}/radar"),
        ProbeCase(name="frontend_calendar", url=f"{frontend_url}/calendar"),
        *stock_html_cases,
        ProbeCase(name="api_health", url=f"{api_url}/api/health"),
        ProbeCase(name="api_countries", url=f"{api_url}/api/countries"),
        ProbeCase(name="api_country_report", url=f"{api_url}/api/country/KR/report"),
        ProbeCase(name="api_heatmap", url=f"{api_url}/api/country/KR/heatmap"),
        ProbeCase(
            name="api_opportunities",
            url=f"{api_url}/api/market/opportunities/KR?{urlencode({'limit': 8})}",
        ),
        ProbeCase(name="api_screener", url=f"{api_url}/api/screener?country=KR&limit=10"),
        *stock_api_cases,
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frontend_url = _normalize_base_url(args.frontend_url)
    api_url = _normalize_base_url(args.api_url)
    stock_tickers = [
        ticker.strip()
        for ticker in str(args.stock_tickers or "").split(",")
        if ticker.strip()
    ]
    cases = build_probe_cases(frontend_url, api_url, stock_tickers)

    print(f"[latency-probe] frontend={frontend_url}")
    print(f"[latency-probe] api={api_url}")
    print(f"[latency-probe] repeats={max(args.repeats, 1)} timeout={max(args.timeout_seconds, 1)}s")
    print()

    for case in cases:
        runs = _measure_case(
            case,
            repeats=max(args.repeats, 1),
            timeout_seconds=max(args.timeout_seconds, 1),
        )
        _print_case(case, runs)

    if not args.skip_diagnostics:
        try:
            _print_diagnostics(api_url, timeout_seconds=max(args.timeout_seconds, 1))
        except Exception as exc:
            print(f"[latency-probe] diagnostics fetch failed: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
