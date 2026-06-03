from __future__ import annotations

from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import Request

from app.errors import SP_6016, SP_6019
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
        "max_requests": 60,
        "window_seconds": 60,
        "label": "아이디 중복 확인",
    },
    "signup_validate": {
        "max_requests": 20,
        "window_seconds": 60,
        "label": "회원가입 검증",
    },
}

_PUBLIC_CONTACT_LIMITS = {
    "min_interval": {
        "max_requests": 1,
        "window_seconds": 8,
        "label": "문의 제출",
    },
    "client_window": {
        "max_requests": 5,
        "window_seconds": 60,
        "label": "문의 제출",
    },
    "email_window": {
        "max_requests": 3,
        "window_seconds": 600,
        "label": "같은 이메일 문의",
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
        headers={"Retry-After": str(retry_after)},
    )


def _raise_contact_rate_limit(label: str, retry_after: int) -> None:
    raise ApiAppException(
        429,
        SP_6019(f"{label} 요청이 너무 많습니다. {retry_after}초 후 다시 시도해 주세요."),
        headers={"Retry-After": str(retry_after)},
    )


def enforce_public_contact_rate_limit(request: Request, normalized_email: str) -> None:
    client_id = get_request_client_identifier(request)

    min_config = _PUBLIC_CONTACT_LIMITS["min_interval"]
    retry_after = _PUBLIC_LIMITER.check(
        key=f"contact:min-interval:{client_id}",
        max_requests=min_config["max_requests"],
        window_seconds=min_config["window_seconds"],
    )
    if retry_after is not None:
        _raise_contact_rate_limit(min_config["label"], retry_after)

    client_config = _PUBLIC_CONTACT_LIMITS["client_window"]
    retry_after = _PUBLIC_LIMITER.check(
        key=f"contact:client-window:{client_id}",
        max_requests=client_config["max_requests"],
        window_seconds=client_config["window_seconds"],
    )
    if retry_after is not None:
        _raise_contact_rate_limit(client_config["label"], retry_after)

    email = normalized_email.strip().lower()
    if not email:
        return

    email_config = _PUBLIC_CONTACT_LIMITS["email_window"]
    retry_after = _PUBLIC_LIMITER.check(
        key=f"contact:email-window:{email}",
        max_requests=email_config["max_requests"],
        window_seconds=email_config["window_seconds"],
    )
    if retry_after is not None:
        _raise_contact_rate_limit(email_config["label"], retry_after)


def reset_public_rate_limit_state() -> None:
    _PUBLIC_LIMITER.reset()
