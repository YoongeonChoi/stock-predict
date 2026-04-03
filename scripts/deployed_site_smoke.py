from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.route_contracts import ApiSmokeCheck, RouteContract, iter_deployed_api_smoke_checks, iter_deployed_frontend_route_contracts


RETRYABLE_STATUSES = {502, 503, 504}


@dataclass(frozen=True)
class FrontendRouteCheck:
    contract: RouteContract
    base: str
    expected_status: int = 200
    timeout: int = 45


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check deployed frontend and API health")
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("STOCK_PREDICT_FRONTEND_URL", "https://www.yoongeon.xyz"),
        help="Base URL for the deployed frontend",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("STOCK_PREDICT_API_URL", "https://api.yoongeon.xyz"),
        help="Base URL for the deployed API",
    )
    parser.add_argument(
        "--expected-version",
        default="",
        help="Expected backend version returned by /api/health",
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
        raise RuntimeError(f"{url} connection failed: {exc}") from exc


def fetch_with_retry(
    url: str,
    *,
    attempts: int = 3,
    timeout: int = 30,
    retry_delay: float = 4.0,
) -> tuple[int, str, dict[str, str]]:
    last_error: Exception | None = None
    last_response: tuple[int, str, dict[str, str]] | None = None

    for attempt in range(1, max(attempts, 1) + 1):
        try:
            response = fetch(url, timeout=timeout)
            status = response[0]
            if status not in RETRYABLE_STATUSES or attempt >= attempts:
                return response
            print(f"[retry] {url} -> {status}, attempt {attempt}/{attempts}")
            last_response = response
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            print(f"[retry] {url} -> {exc}, attempt {attempt}/{attempts}")

        time.sleep(retry_delay * attempt)

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{url} returned no usable response")


def preview(text: str, limit: int = 180) -> str:
    return " ".join(text.split())[:limit]


def build_api_checks(api_url: str) -> list[tuple[ApiSmokeCheck, str]]:
    return [
        (check, urljoin(f"{api_url}/", check.path.lstrip("/")))
        for check in iter_deployed_api_smoke_checks()
    ]


def build_frontend_checks(frontend_url: str) -> list[tuple[FrontendRouteCheck, str]]:
    return [
        (
            FrontendRouteCheck(contract=contract, base=frontend_url),
            urljoin(f"{frontend_url}/", contract.route.lstrip("/")),
        )
        for contract in iter_deployed_frontend_route_contracts()
    ]


def validate_frontend_html(check: FrontendRouteCheck, body: str) -> str | None:
    if "<html" not in body:
        return "missing <html in response body"

    forbidden_hits = [text for text in check.contract.smoke.forbidden_texts if text in body]
    if forbidden_hits:
        return f"forbidden text {forbidden_hits}"

    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    frontend_url = args.frontend_url.rstrip("/")
    api_url = args.api_url.rstrip("/")

    failures: list[str] = []
    health_payload: dict[str, Any] | None = None

    print("[deployed-smoke] starting deployed smoke")
    print(f"[deployed-smoke] frontend={frontend_url}")
    print(f"[deployed-smoke] api={api_url}")

    for check, url in build_api_checks(api_url):
        try:
            status, body, _headers = fetch_with_retry(url, attempts=3, timeout=check.timeout)
        except Exception as exc:
            failures.append(f"{check.name}: {exc}")
            print(f"[FAIL] {check.name:24} {url} -> {exc}")
            continue

        if status != check.expected_status:
            failures.append(f"{check.name}: expected {check.expected_status}, got {status} ({preview(body)})")
            print(f"[FAIL] {check.name:24} {url} -> {status} ({preview(body)})")
            continue

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            failures.append(f"{check.name}: invalid JSON ({preview(body)})")
            print(f"[FAIL] {check.name:24} {url} -> invalid JSON")
            continue

        if check.name == "health" and isinstance(payload, dict):
            health_payload = payload

        if check.expected_error_code and (
            not isinstance(payload, dict) or payload.get("error_code") != check.expected_error_code
        ):
            failures.append(f"{check.name}: expected error_code {check.expected_error_code}, got {payload}")
            print(f"[FAIL] {check.name:24} {url} -> missing error_code {check.expected_error_code}")
            continue

        print(f"[OK]   {check.name:24} {url} -> {status}")

    for check, url in build_frontend_checks(frontend_url):
        try:
            status, body, _headers = fetch_with_retry(url, attempts=3, timeout=check.timeout)
        except Exception as exc:
            failures.append(f"frontend-{check.contract.key}: {exc}")
            print(f"[FAIL] frontend-{check.contract.key:15} {url} -> {exc}")
            continue

        if status != check.expected_status:
            failures.append(
                f"frontend-{check.contract.key}: expected {check.expected_status}, got {status} ({preview(body)})"
            )
            print(f"[FAIL] frontend-{check.contract.key:15} {url} -> {status} ({preview(body)})")
            continue

        validation_error = validate_frontend_html(check, body)
        if validation_error:
            failures.append(f"frontend-{check.contract.key}: {validation_error}")
            print(f"[FAIL] frontend-{check.contract.key:15} {url} -> {validation_error}")
            continue

        print(f"[OK]   frontend-{check.contract.key:15} {url} -> {status}")

    if args.expected_version and health_payload:
        current_version = str(health_payload.get("version", ""))
        if current_version != args.expected_version:
            failures.append(f"health version mismatch: expected {args.expected_version}, got {current_version}")
            print(f"[FAIL] health-version            expected {args.expected_version}, got {current_version}")
        else:
            print(f"[OK]   health-version            {current_version}")

    if health_payload:
        print(f"[info] deployed health version={health_payload.get('version')} status={health_payload.get('status')}")

    if failures:
        print("\n[deployed-smoke] failures detected:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n[deployed-smoke] all deployed checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
