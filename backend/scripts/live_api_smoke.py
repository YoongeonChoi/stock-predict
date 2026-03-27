from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.main import app


@dataclass(frozen=True)
class ApiCheck:
    method: str
    path: str
    expected_status: int = 200
    expected_error_code: str | None = None
    json_body: dict | None = None


CHECKS = [
    ApiCheck("GET", "/api/health"),
    ApiCheck("GET", "/api/countries"),
    ApiCheck("GET", "/api/country/KR/report"),
    ApiCheck("GET", "/api/country/KR/heatmap"),
    ApiCheck("GET", "/api/country/KR/report/pdf"),
    ApiCheck("GET", "/api/country/KR/report/csv"),
    ApiCheck("GET", "/api/country/KR/forecast"),
    ApiCheck("GET", "/api/market/indicators"),
    ApiCheck("GET", "/api/country/KR/sector-performance"),
    ApiCheck("GET", "/api/country/KR/sectors"),
    ApiCheck("GET", "/api/market/movers/KR"),
    ApiCheck("GET", "/api/market/opportunities/KR?limit=12"),
    ApiCheck("GET", "/api/country/KR/sector/information_technology/report"),
    ApiCheck("GET", "/api/stock/AAPL/detail"),
    ApiCheck("GET", "/api/stock/AAPL/chart"),
    ApiCheck("GET", "/api/stock/AAPL/technical-summary"),
    ApiCheck("GET", "/api/stock/AAPL/pivot-points"),
    ApiCheck("GET", "/api/search?q=apple"),
    ApiCheck("GET", "/api/watchlist", expected_status=401, expected_error_code="SP-6014"),
    ApiCheck("POST", "/api/watchlist/AAPL?country_code=US", expected_status=401, expected_error_code="SP-6014"),
    ApiCheck("DELETE", "/api/watchlist/AAPL", expected_status=401, expected_error_code="SP-6014"),
    ApiCheck("GET", "/api/compare?tickers=AAPL,MSFT"),
    ApiCheck("GET", "/api/archive"),
    ApiCheck("GET", "/api/archive/accuracy/stats"),
    ApiCheck("GET", "/api/archive/research?region_code=KR&limit=20&auto_refresh=false"),
    ApiCheck("GET", "/api/archive/research/status"),
    ApiCheck("POST", "/api/archive/research/refresh"),
    ApiCheck("GET", "/api/calendar/KR?year=2026&month=3"),
    ApiCheck("GET", "/api/screener?country=KR&limit=20"),
    ApiCheck("GET", "/api/portfolio", expected_status=401, expected_error_code="SP-6014"),
    ApiCheck("GET", "/api/portfolio/ideal?refresh=false&history_limit=10"),
    ApiCheck("GET", "/api/system/diagnostics"),
    ApiCheck("GET", "/api/research/predictions?limit_recent=20&refresh=false"),
    ApiCheck("POST", "/api/portfolio/holdings", expected_status=401, expected_error_code="SP-6014", json_body={"ticker": "AAPL"}),
    ApiCheck("GET", "/api/does-not-exist", expected_status=404, expected_error_code="SP-6011"),
]


def main() -> int:
    failures = []
    print("[live-smoke] starting full API sweep")
    with TestClient(app) as client:
        for check in CHECKS:
            started = time.perf_counter()
            response = client.request(check.method, check.path, json=check.json_body)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            ok = response.status_code == check.expected_status
            marker = "OK" if ok else "FAIL"
            extra = ""
            try:
                payload = response.json()
                if isinstance(payload, dict) and payload.get("error_code"):
                    extra = f" {payload['error_code']}"
            except Exception:
                payload = None
            error_code_ok = True
            if check.expected_error_code:
                error_code_ok = isinstance(payload, dict) and payload.get("error_code") == check.expected_error_code
            print(f"[{marker}] {check.method:6} {check.path} -> {response.status_code} in {duration_ms}ms{extra}")
            if not ok or not error_code_ok:
                body_preview = response.text[:300]
                failures.append((check, response.status_code, body_preview))

    if failures:
        print("\n[live-smoke] failures detected:")
        for check, status_code, preview in failures:
            suffix = f" and error_code {check.expected_error_code}" if check.expected_error_code else ""
            print(f"- {check.method} {check.path} expected {check.expected_status}{suffix}, got {status_code}: {preview}")
        return 1

    print("\n[live-smoke] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
