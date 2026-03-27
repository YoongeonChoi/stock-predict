from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class HttpCheck:
    name: str
    base: str
    path: str
    expected_status: int
    expect_json: bool = False
    expected_error_code: str | None = None
    contains_text: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="운영 배포 사이트 스모크 점검")
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("STOCK_PREDICT_FRONTEND_URL", "https://www.yoongeon.xyz"),
        help="운영 프론트엔드 기본 URL",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("STOCK_PREDICT_API_URL", "https://api.yoongeon.xyz"),
        help="운영 백엔드 기본 URL",
    )
    parser.add_argument(
        "--expected-version",
        default="",
        help="지정하면 /api/health 응답의 version과 일치하는지 확인합니다.",
    )
    return parser.parse_args(argv)


def fetch(url: str, timeout: int = 30) -> tuple[int, str, dict[str, str]]:
    request = Request(url, headers={"User-Agent": "stock-predict-deployed-smoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body, dict(response.headers.items())
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body, dict(exc.headers.items())
    except URLError as exc:
        raise RuntimeError(f"{url} 연결 실패: {exc}") from exc


def preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frontend_url = args.frontend_url.rstrip("/")
    api_url = args.api_url.rstrip("/")

    checks = [
        HttpCheck("health", api_url, "/api/health", expected_status=200, expect_json=True),
        HttpCheck("countries", api_url, "/api/countries", expected_status=200, expect_json=True),
        HttpCheck(
            "watchlist-auth",
            api_url,
            "/api/watchlist",
            expected_status=401,
            expect_json=True,
            expected_error_code="SP-6014",
        ),
        HttpCheck("market-indicators", api_url, "/api/market/indicators", expected_status=200, expect_json=True),
        HttpCheck("frontend-home", frontend_url, "/", expected_status=200, contains_text="<html"),
        HttpCheck("frontend-auth", frontend_url, "/auth", expected_status=200, contains_text="<html"),
        HttpCheck("frontend-settings", frontend_url, "/settings", expected_status=200, contains_text="<html"),
    ]

    failures: list[str] = []
    health_payload: dict[str, Any] | None = None

    print("[deployed-smoke] 운영 사이트 확인 시작")
    print(f"[deployed-smoke] frontend={frontend_url}")
    print(f"[deployed-smoke] api={api_url}")

    for check in checks:
        url = urljoin(f"{check.base}/", check.path.lstrip("/"))
        try:
            status, body, _headers = fetch(url)
        except Exception as exc:
            failures.append(f"{check.name}: {exc}")
            print(f"[FAIL] {check.name:18} {url} -> {exc}")
            continue

        if status != check.expected_status:
            failures.append(
                f"{check.name}: expected {check.expected_status}, got {status} ({preview(body)})"
            )
            print(f"[FAIL] {check.name:18} {url} -> {status} ({preview(body)})")
            continue

        if check.expect_json:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                failures.append(f"{check.name}: JSON 응답이 아닙니다. ({preview(body)})")
                print(f"[FAIL] {check.name:18} {url} -> invalid JSON")
                continue

            if check.name == "health" and isinstance(payload, dict):
                health_payload = payload

            if check.expected_error_code and (
                not isinstance(payload, dict) or payload.get("error_code") != check.expected_error_code
            ):
                failures.append(
                    f"{check.name}: expected error_code {check.expected_error_code}, got {payload}"
                )
                print(f"[FAIL] {check.name:18} {url} -> missing error_code {check.expected_error_code}")
                continue

        if check.contains_text and check.contains_text not in body:
            failures.append(f"{check.name}: expected body to include {check.contains_text!r}")
            print(f"[FAIL] {check.name:18} {url} -> missing text {check.contains_text!r}")
            continue

        print(f"[OK]   {check.name:18} {url} -> {status}")

    if args.expected_version and health_payload:
        current_version = str(health_payload.get("version", ""))
        if current_version != args.expected_version:
            failures.append(
                f"health version mismatch: expected {args.expected_version}, got {current_version}"
            )
            print(
                f"[FAIL] health-version      expected {args.expected_version}, got {current_version}"
            )
        else:
            print(f"[OK]   health-version      {current_version}")

    if health_payload:
        print(
            f"[info] 배포 health version={health_payload.get('version')} status={health_payload.get('status')}"
        )

    if failures:
        print("\n[deployed-smoke] 실패 항목:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[deployed-smoke] 모든 운영 사이트 점검 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
