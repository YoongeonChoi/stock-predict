from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.route_contracts import ReversibleAuthWriteCheck, iter_reversible_auth_write_checks


DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_TOKEN_ENV = "STOCK_PREDICT_SMOKE_BEARER_TOKEN"
WATCHLIST_CANDIDATES = ("005930.KS", "000660.KS", "035420.KS", "051910.KS")
PORTFOLIO_CANDIDATES = ("005930.KS", "000660.KS", "035420.KS", "051910.KS")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reversible authenticated write smoke checks")
    parser.add_argument(
        "--api-url",
        default=os.getenv("STOCK_PREDICT_API_URL", DEFAULT_API_URL),
        help="Base URL for the API",
    )
    parser.add_argument(
        "--token-env",
        default=DEFAULT_TOKEN_ENV,
        help="Environment variable containing the bearer token",
    )
    return parser.parse_args(argv)


def fetch_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str,
    payload: dict | None = None,
) -> tuple[int, dict | list | None]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "stock-predict-reversible-auth-smoke/1.0",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw) if raw else None
        return exc.code, parsed


def ensure_ok(status: int, payload: dict | list | None, label: str) -> None:
    if not (200 <= status < 300):
        raise RuntimeError(f"{label} failed with {status}: {payload}")


def run_watchlist_flow(base_url: str, token: str) -> str:
    status, payload = fetch_json(base_url, "/api/watchlist", token=token)
    ensure_ok(status, payload, "watchlist list")
    items = payload if isinstance(payload, list) else []
    existing = {str(item.get("ticker")) for item in items if isinstance(item, dict)}
    ticker = next((candidate for candidate in WATCHLIST_CANDIDATES if candidate not in existing), "")
    if not ticker:
        return "skip: all watchlist candidates already exist"

    qs = urlencode({"country_code": "KR"})
    status, payload = fetch_json(base_url, f"/api/watchlist/{ticker}?{qs}", method="POST", token=token)
    ensure_ok(status, payload, "watchlist add")

    status, payload = fetch_json(base_url, f"/api/watchlist/{ticker}", method="DELETE", token=token)
    ensure_ok(status, payload, "watchlist remove")
    return f"ok: add/remove {ticker}"


def run_portfolio_flow(base_url: str, token: str) -> str:
    status, payload = fetch_json(base_url, "/api/portfolio", token=token)
    ensure_ok(status, payload, "portfolio get")
    holdings = payload.get("holdings", []) if isinstance(payload, dict) else []
    existing = {str(item.get("ticker")) for item in holdings if isinstance(item, dict)}
    ticker = next((candidate for candidate in PORTFOLIO_CANDIDATES if candidate not in existing), "")
    if not ticker:
        return "skip: all portfolio candidates already exist"

    buy_date = date.today().isoformat()
    create_payload = {
        "ticker": ticker,
        "buy_price": 12345.67,
        "quantity": 0.01,
        "buy_date": buy_date,
        "country_code": "KR",
    }
    status, payload = fetch_json(
        base_url,
        "/api/portfolio/holdings",
        method="POST",
        token=token,
        payload=create_payload,
    )
    ensure_ok(status, payload, "portfolio holding add")

    status, payload = fetch_json(base_url, "/api/portfolio", token=token)
    ensure_ok(status, payload, "portfolio refresh")
    holdings = payload.get("holdings", []) if isinstance(payload, dict) else []
    created = next(
        (
            item
            for item in holdings
            if isinstance(item, dict)
            and str(item.get("ticker")) == ticker
            and str(item.get("buy_date")) == buy_date
            and abs(float(item.get("buy_price") or 0.0) - 12345.67) < 1e-6
        ),
        None,
    )
    if not created:
        raise RuntimeError(f"portfolio add succeeded but no created holding was found for {ticker}")

    holding_id = int(created["id"])
    update_payload = dict(create_payload)
    update_payload["quantity"] = 0.02
    status, payload = fetch_json(
        base_url,
        f"/api/portfolio/holdings/{holding_id}",
        method="PUT",
        token=token,
        payload=update_payload,
    )
    ensure_ok(status, payload, "portfolio holding update")

    status, payload = fetch_json(
        base_url,
        f"/api/portfolio/holdings/{holding_id}",
        method="DELETE",
        token=token,
    )
    ensure_ok(status, payload, "portfolio holding delete")
    return f"ok: add/update/delete {ticker}"


def run_settings_profile_flow(base_url: str, token: str) -> str:
    status, payload = fetch_json(base_url, "/api/account/me", token=token)
    ensure_ok(status, payload, "account get")
    if not isinstance(payload, dict):
        return "skip: account profile payload missing"

    username = str(payload.get("username") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    phone_number = str(payload.get("phone_number") or "").strip()
    birth_date = str(payload.get("birth_date") or "").strip()
    if not username or not full_name or not phone_number or not birth_date:
        return "skip: account profile fields missing"

    temporary_name = f"{full_name} smoke"
    if temporary_name == full_name:
        temporary_name = f"{full_name} A"

    update_payload = {
        "username": username,
        "full_name": temporary_name,
        "phone_number": phone_number,
        "birth_date": birth_date,
    }
    status, update_result = fetch_json(
        base_url,
        "/api/account/me",
        method="PATCH",
        token=token,
        payload=update_payload,
    )
    ensure_ok(status, update_result, "account profile temporary update")

    revert_payload = {
        "username": username,
        "full_name": full_name,
        "phone_number": phone_number,
        "birth_date": birth_date,
    }
    status, revert_result = fetch_json(
        base_url,
        "/api/account/me",
        method="PATCH",
        token=token,
        payload=revert_payload,
    )
    ensure_ok(status, revert_result, "account profile revert")
    return "ok: temporary profile update reverted"


FLOW_RUNNERS = {
    "watchlist-write": run_watchlist_flow,
    "portfolio-holding-write": run_portfolio_flow,
    "settings-profile-write": run_settings_profile_flow,
}


def run_check(check: ReversibleAuthWriteCheck, base_url: str, token: str) -> str:
    runner = FLOW_RUNNERS.get(check.name)
    if runner is None:
        raise RuntimeError(f"no reversible auth smoke runner is registered for {check.name}")
    return runner(base_url, token)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_url = args.api_url
    token = os.getenv(args.token_env, "").strip()
    if not token:
        print(f"[auth-write-smoke] skip: {args.token_env} is not configured")
        return 0

    try:
        print(f"[auth-write-smoke] api={base_url}")
        for check in iter_reversible_auth_write_checks():
            result = run_check(check, base_url, token)
            print(f"[auth-write-smoke] {check.name} -> {result}")
        print("[auth-write-smoke] all reversible flows passed")
        return 0
    except Exception as exc:
        print(f"[auth-write-smoke] fail: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
