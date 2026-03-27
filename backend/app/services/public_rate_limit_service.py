from __future__ import annotations

from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import Request

from app.errors import SP_6016
from app.exceptions import ApiAppException


class SlidingWindowRateLimiter:
    def __init__(self, *, time_fn=monotonic):
        self._time_fn = time_fn
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def check(self, *, key: str, max_requests: int, window_seconds: int) -> int | None:
        now = self._time_fn()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_requests:
                retry_after = max(bucket[0] + window_seconds - now, 0)
                return max(1, ceil(retry_after))

            bucket.append(now)
            return None


_PUBLIC_LIMITER = SlidingWindowRateLimiter()

_PUBLIC_ACCOUNT_LIMITS = {
    "username_availability": {
        "max_requests": 12,
        "window_seconds": 60,
        "label": "아이디 중복 확인",
    },
    "signup_validate": {
        "max_requests": 6,
        "window_seconds": 60,
        "label": "회원가입 검증",
    },
}


def get_request_client_identifier(request: Request) -> str:
    cloudflare_ip = (request.headers.get("cf-connecting-ip") or "").strip()
    if cloudflare_ip:
        return cloudflare_ip

    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def enforce_public_account_rate_limit(request: Request, scope: str) -> None:
    config = _PUBLIC_ACCOUNT_LIMITS[scope]
    client_id = get_request_client_identifier(request)
    retry_after = _PUBLIC_LIMITER.check(
        key=f"public-account:{scope}:{client_id}",
        max_requests=config["max_requests"],
        window_seconds=config["window_seconds"],
    )
    if retry_after is None:
        return

    raise ApiAppException(
        429,
        SP_6016(
            (
                f"{config['label']} 요청이 너무 많습니다. "
                f"{retry_after}초 후 다시 시도해 주세요."
            )
        ),
    )


def reset_public_rate_limit_state() -> None:
    _PUBLIC_LIMITER.reset()
