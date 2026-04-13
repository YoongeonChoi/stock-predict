from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from scripts.route_contracts import ApiSmokeCheck, iter_live_api_smoke_checks


CHECKS = tuple(iter_live_api_smoke_checks())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local API smoke checks from the route registry")
    return parser.parse_args(argv)


def preview(text: str, limit: int = 300) -> str:
    return " ".join(text.split())[:limit]


def main(argv: list[str] | None = None) -> int:
    parse_args(argv)
    failures: list[tuple[ApiSmokeCheck, int, str]] = []

    print("[live-smoke] starting API sweep from route registry")
    with TestClient(app) as client:
        for check in CHECKS:
            started = time.perf_counter()
            response = client.request(check.method, check.path, json=check.json_body)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)

            payload = None
            extra = ""
            try:
                payload = response.json()
            except Exception:
                payload = None
            else:
                if isinstance(payload, dict) and payload.get("error_code"):
                    extra = f" {payload['error_code']}"

            status_ok = response.status_code == check.expected_status
            error_code_ok = True
            if check.expected_error_code:
                error_code_ok = isinstance(payload, dict) and payload.get("error_code") == check.expected_error_code

            marker = "OK" if status_ok and error_code_ok else "FAIL"
            print(
                f"[{marker}] {check.name:24} {check.method:6} {check.path} "
                f"-> {response.status_code} in {duration_ms}ms{extra}"
            )

            if not status_ok or not error_code_ok:
                failures.append((check, response.status_code, preview(response.text)))

    if failures:
        print("\n[live-smoke] failures detected:")
        for check, status_code, body_preview in failures:
            suffix = f" and error_code {check.expected_error_code}" if check.expected_error_code else ""
            print(
                f"- {check.name}: {check.method} {check.path} "
                f"expected {check.expected_status}{suffix}, got {status_code}: {body_preview}"
            )
        return 1

    print("\n[live-smoke] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
