from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "backend" / "app" / "version.py"


def read_local_version() -> str:
    namespace: dict[str, Any] = {}
    source = VERSION_FILE.read_text(encoding="utf-8")
    exec(source, namespace)
    version = str(namespace.get("APP_VERSION", "")).strip()
    if not version:
        raise RuntimeError("backend/app/version.py 에서 APP_VERSION을 읽을 수 없습니다.")
    return version


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="운영 배포 버전 반영 대기")
    parser.add_argument(
        "--api-url",
        default=os.getenv("STOCK_PREDICT_API_URL", "https://api.yoongeon.xyz"),
        help="운영 백엔드 기본 URL",
    )
    parser.add_argument(
        "--expected-version",
        default="",
        help="기대하는 배포 버전. 비워두면 로컬 backend/app/version.py 값을 사용합니다.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=600, help="최대 대기 시간(초)")
    parser.add_argument("--interval-seconds", type=int, default=15, help="재확인 간격(초)")
    return parser.parse_args(argv)


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "stock-predict-version-waiter/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url} 연결 실패: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_version = args.expected_version.strip() or read_local_version()
    health_url = args.api_url.rstrip("/") + "/api/health"
    deadline = time.time() + max(args.timeout_seconds, 1)
    last_version = ""
    last_status = ""
    attempt = 0

    print(f"[deploy-wait] expected_version={expected_version}")
    print(f"[deploy-wait] health_url={health_url}")

    while time.time() <= deadline:
        attempt += 1
        try:
            payload = fetch_json(health_url)
            last_version = str(payload.get("version", ""))
            last_status = str(payload.get("status", ""))
            print(
                f"[deploy-wait] attempt={attempt} version={last_version or '-'} "
                f"status={last_status or '-'}"
            )
            if last_version == expected_version and last_status == "ok":
                print("[deploy-wait] 운영 배포가 기대 버전으로 반영되었습니다.")
                return 0
        except Exception as exc:
            print(f"[deploy-wait] attempt={attempt} error={exc}")

        if time.time() + args.interval_seconds > deadline:
            break
        time.sleep(max(args.interval_seconds, 1))

    print(
        "[deploy-wait] 시간 내 반영을 확인하지 못했습니다. "
        f"last_version={last_version or '-'} last_status={last_status or '-'}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
