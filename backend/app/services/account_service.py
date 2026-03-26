from __future__ import annotations

import re
from datetime import date

from app.auth import AuthenticatedUser
from app.models.account import AccountProfile, UsernameAvailabilityResponse
from app.data.supabase_client import supabase_client

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{3,19}$")
PHONE_DIGIT_PATTERN = re.compile(r"^\d{9,15}$")
FULL_NAME_PATTERN = re.compile(r"^[A-Za-z가-힣\s]{2,40}$")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(username.strip()))


def normalize_phone_number(phone_number: str | None) -> str | None:
    if not phone_number:
        return None
    digits = re.sub(r"\D", "", phone_number)
    return digits or None


def normalize_full_name(full_name: str | None) -> str | None:
    if not full_name:
        return None
    compact = " ".join(full_name.split())
    return compact or None


def is_valid_full_name(full_name: str | None) -> bool:
    normalized = normalize_full_name(full_name)
    return bool(normalized and FULL_NAME_PATTERN.fullmatch(normalized))


def is_valid_phone_number(phone_number: str | None) -> bool:
    normalized = normalize_phone_number(phone_number)
    return bool(normalized and PHONE_DIGIT_PATTERN.fullmatch(normalized))


def format_phone_number(phone_number: str | None) -> str | None:
    digits = normalize_phone_number(phone_number)
    if not digits:
        return None
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return digits


def mask_phone_number(phone_number: str | None) -> str | None:
    digits = normalize_phone_number(phone_number)
    if not digits:
        return None
    if len(digits) == 11:
        return f"{digits[:3]}-****-{digits[-4:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-***-{digits[-4:]}"
    return f"{digits[:3]}***{digits[-2:]}" if len(digits) > 5 else digits


def is_valid_birth_date(birth_date: str | None) -> bool:
    if not birth_date:
        return False
    try:
        parsed = date.fromisoformat(birth_date)
    except ValueError:
        return False
    return date(1900, 1, 1) <= parsed < date.today()


def build_account_profile(user: AuthenticatedUser) -> AccountProfile:
    return AccountProfile(
        user_id=user.id,
        email=user.email,
        username=normalize_username(user.username or "") or None,
        full_name=(user.full_name or "").strip() or None,
        phone_number=format_phone_number(user.phone_number),
        phone_masked=mask_phone_number(user.phone_number),
        birth_date=user.birth_date,
    )


async def get_current_profile(user: AuthenticatedUser) -> AccountProfile:
    return build_account_profile(user)


async def check_username_availability(
    username: str,
    *,
    exclude_user_id: str | None = None,
) -> UsernameAvailabilityResponse:
    normalized = normalize_username(username)
    if not normalized:
        return UsernameAvailabilityResponse(
            username=username,
            normalized_username="",
            valid=False,
            available=False,
            message="아이디를 입력해 주세요.",
        )
    if not is_valid_username(username):
        return UsernameAvailabilityResponse(
            username=username,
            normalized_username=normalized,
            valid=False,
            available=False,
            message="아이디는 영문 소문자로 시작하고, 영문 소문자·숫자·밑줄만 4~20자까지 사용할 수 있습니다.",
        )

    existing = await supabase_client.find_user_by_username(normalized)
    available = existing is None or str(existing.get("id") or "") == (exclude_user_id or "")
    return UsernameAvailabilityResponse(
        username=username,
        normalized_username=normalized,
        valid=True,
        available=available,
        message="사용 가능한 아이디입니다." if available else "이미 사용 중인 아이디입니다.",
    )
