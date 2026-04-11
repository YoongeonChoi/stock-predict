from __future__ import annotations

import argparse
import json
import os
import socket
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
DEFAULT_API_TIMEOUT_SECONDS = 15
DEFAULT_FRONTEND_TIMEOUT_SECONDS = 20
DEFAULT_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SECONDS = 1.5


@dataclass(frozen=True)
class FrontendRouteCheck:
    contract: RouteContract
    base: str
    expected_status: int = 200
    timeout: int = 45


@dataclass(frozen=True)
class FetchOutcome:
    status: int
    body: str
    headers: dict[str, str]
    attempts: int
    total_elapsed_seconds: float
    final_attempt_elapsed_seconds: float


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
    parser.add_argument(
        "--api-timeout",
        type=int,
        default=DEFAULT_API_TIMEOUT_SECONDS,
        help="Upper bound for each deployed API request timeout in seconds",
    )
    parser.add_argument(
        "--frontend-timeout",
        type=int,
        default=DEFAULT_FRONTEND_TIMEOUT_SECONDS,
        help="Upper bound for each deployed frontend request timeout in seconds",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help="How many times to retry each deployed request",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="Base retry delay in seconds before the next attempt",
    )
    parser.add_argument(
        "--max-total-seconds",
        type=float,
        default=0.0,
        help="Optional total wall-clock budget for the full deployed smoke run",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first deployed check failure",
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
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"{url} timed out after {timeout}s") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} connection failed: {exc}") from exc


def clamp_timeout(request_timeout: int, timeout_cap: int) -> int:
    return max(1, min(max(1, request_timeout), max(1, timeout_cap)))


def remaining_budget_seconds(deadline: float | None) -> float | None:
    if deadline is None:
        return None
    return deadline - time.monotonic()


def fetch_with_retry(
    url: str,
    *,
    attempts: int = 3,
    timeout: int = 30,
    retry_delay: float = 4.0,
    deadline: float | None = None,
) -> FetchOutcome:
    last_error: Exception | None = None
    last_response: tuple[int, str, dict[str, str]] | None = None
    overall_started = time.monotonic()
    last_attempt_elapsed = 0.0

    for attempt in range(1, max(attempts, 1) + 1):
        remaining = remaining_budget_seconds(deadline)
        if remaining is not None and remaining <= 0:
            raise RuntimeError(f"{url} skipped because the deployed smoke budget was exhausted")
        attempt_timeout = timeout
        if remaining is not None:
            attempt_timeout = max(1, min(timeout, int(remaining)))
        attempt_started = time.monotonic()
        try:
            response = fetch(url, timeout=attempt_timeout)
            last_attempt_elapsed = time.monotonic() - attempt_started
            status = response[0]
            if status not in RETRYABLE_STATUSES or attempt >= attempts:
                return FetchOutcome(
                    status=status,
                    body=response[1],
                    headers=response[2],
                    attempts=attempt,
                    total_elapsed_seconds=time.monotonic() - overall_started,
                    final_attempt_elapsed_seconds=last_attempt_elapsed,
                )
            print(
                f"[retry] {url} -> {status}, attempt {attempt}/{attempts} attempt_elapsed={last_attempt_elapsed:.2f}s",
                flush=True,
            )
            last_response = response
        except Exception as exc:
            last_attempt_elapsed = time.monotonic() - attempt_started
            last_error = exc
            if attempt >= attempts:
                raise
            print(
                f"[retry] {url} -> {exc}, attempt {attempt}/{attempts} attempt_elapsed={last_attempt_elapsed:.2f}s",
                flush=True,
            )

        time.sleep(retry_delay * attempt)

    if last_response is not None:
        return FetchOutcome(
            status=last_response[0],
            body=last_response[1],
            headers=last_response[2],
            attempts=max(attempts, 1),
            total_elapsed_seconds=time.monotonic() - overall_started,
            final_attempt_elapsed_seconds=last_attempt_elapsed,
        )
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"{url} returned no usable response")


def format_elapsed_summary(outcome: FetchOutcome) -> str:
    if outcome.attempts <= 1:
        return f"in {outcome.final_attempt_elapsed_seconds:.2f}s"
    return (
        f"in {outcome.total_elapsed_seconds:.2f}s "
        f"(attempts={outcome.attempts}, final_attempt={outcome.final_attempt_elapsed_seconds:.2f}s)"
    )


def preview(text: str, limit: int = 180) -> str:
    return " ".join(text.split())[:limit]


def summarize_api_payload(check: ApiSmokeCheck, payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    details: list[str] = []
    if "partial" in payload:
        details.append(f"partial={payload.get('partial')}")
    fallback_reason = payload.get("fallback_reason")
    if fallback_reason:
        details.append(f"fallback={fallback_reason}")

    memory = payload.get("memory_diagnostics") or payload.get("memory")
    if check.name == "diagnostics" and isinstance(memory, dict):
        rss_mb = memory.get("rss_mb")
        cgroup_mb = memory.get("cgroup_current_mb")
        pressure = memory.get("pressure_ratio")
        state = memory.get("pressure_state")
        if rss_mb is not None:
            details.append(f"rss={rss_mb}MB")
        if cgroup_mb is not None:
            details.append(f"cgroup={cgroup_mb}MB")
        if pressure is not None:
            details.append(f"pressure={pressure}")
        if state:
            details.append(f"state={state}")

    return " ".join(details)


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


def _report_failures(failures: list[str]) -> int:
    print("\n[deployed-smoke] failures detected:", flush=True)
    for failure in failures:
        print(f"- {failure}", flush=True)
    return 1


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
    deadline = time.monotonic() + args.max_total_seconds if args.max_total_seconds and args.max_total_seconds > 0 else None

    print("[deployed-smoke] starting deployed smoke", flush=True)
    print(f"[deployed-smoke] frontend={frontend_url}", flush=True)
    print(f"[deployed-smoke] api={api_url}", flush=True)

    for check, url in build_api_checks(api_url):
        timeout = clamp_timeout(check.timeout, args.api_timeout)
        print(
            f"[check] {check.name:24} {url} timeout={timeout}s attempts={max(1, args.attempts)}",
            flush=True,
        )
        try:
            outcome = fetch_with_retry(
                url,
                attempts=max(1, args.attempts),
                timeout=timeout,
                retry_delay=max(0.0, args.retry_delay),
                deadline=deadline,
            )
        except Exception as exc:
            failures.append(f"{check.name}: {exc}")
            print(f"[FAIL] {check.name:24} {url} -> {exc}", flush=True)
            if args.fail_fast:
                return _report_failures(failures)
            continue
        status, body = outcome.status, outcome.body

        if status != check.expected_status:
            failures.append(f"{check.name}: expected {check.expected_status}, got {status} ({preview(body)})")
            print(
                f"[FAIL] {check.name:24} {url} -> {status} ({preview(body)}) {format_elapsed_summary(outcome)}",
                flush=True,
            )
            if args.fail_fast:
                return _report_failures(failures)
            continue

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            failures.append(f"{check.name}: invalid JSON ({preview(body)})")
            print(
                f"[FAIL] {check.name:24} {url} -> invalid JSON {format_elapsed_summary(outcome)}",
                flush=True,
            )
            if args.fail_fast:
                return _report_failures(failures)
            continue

        if check.name == "health" and isinstance(payload, dict):
            health_payload = payload

        if check.expected_error_code and (
            not isinstance(payload, dict) or payload.get("error_code") != check.expected_error_code
        ):
            failures.append(f"{check.name}: expected error_code {check.expected_error_code}, got {payload}")
            print(
                f"[FAIL] {check.name:24} {url} -> missing error_code {check.expected_error_code} in {elapsed:.2f}s",
                flush=True,
            )
            if args.fail_fast:
                return _report_failures(failures)
            continue

        payload_summary = summarize_api_payload(check, payload)
        suffix = f" {payload_summary}" if payload_summary else ""
        print(
            f"[OK]   {check.name:24} {url} -> {status} {format_elapsed_summary(outcome)}{suffix}",
            flush=True,
        )

    for check, url in build_frontend_checks(frontend_url):
        timeout = clamp_timeout(check.timeout, args.frontend_timeout)
        print(
            f"[check] frontend-{check.contract.key:15} {url} timeout={timeout}s attempts={max(1, args.attempts)}",
            flush=True,
        )
        try:
            outcome = fetch_with_retry(
                url,
                attempts=max(1, args.attempts),
                timeout=timeout,
                retry_delay=max(0.0, args.retry_delay),
                deadline=deadline,
            )
        except Exception as exc:
            failures.append(f"frontend-{check.contract.key}: {exc}")
            print(f"[FAIL] frontend-{check.contract.key:15} {url} -> {exc}", flush=True)
            if args.fail_fast:
                return _report_failures(failures)
            continue
        status, body = outcome.status, outcome.body

        if status != check.expected_status:
            failures.append(
                f"frontend-{check.contract.key}: expected {check.expected_status}, got {status} ({preview(body)})"
            )
            print(
                f"[FAIL] frontend-{check.contract.key:15} {url} -> {status} ({preview(body)}) {format_elapsed_summary(outcome)}",
                flush=True,
            )
            if args.fail_fast:
                return _report_failures(failures)
            continue

        validation_error = validate_frontend_html(check, body)
        if validation_error:
            failures.append(f"frontend-{check.contract.key}: {validation_error}")
            print(
                f"[FAIL] frontend-{check.contract.key:15} {url} -> {validation_error} {format_elapsed_summary(outcome)}",
                flush=True,
            )
            if args.fail_fast:
                return _report_failures(failures)
            continue

        print(
            f"[OK]   frontend-{check.contract.key:15} {url} -> {status} {format_elapsed_summary(outcome)}",
            flush=True,
        )

    if args.expected_version and health_payload:
        current_version = str(health_payload.get("version", ""))
        if current_version != args.expected_version:
            failures.append(f"health version mismatch: expected {args.expected_version}, got {current_version}")
            print(f"[FAIL] health-version            expected {args.expected_version}, got {current_version}", flush=True)
        else:
            print(f"[OK]   health-version            {current_version}", flush=True)

    if health_payload:
        print(
            f"[info] deployed health version={health_payload.get('version')} status={health_payload.get('status')}",
            flush=True,
        )

    if failures:
        return _report_failures(failures)

    print("\n[deployed-smoke] all deployed checks passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
