from __future__ import annotations

import re
from datetime import date

from app.auth import AuthenticatedUser
from app.errors import SP_6015
from app.exceptions import ApiAppException
from app.models.account import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    AccountProfile,
    AccountProfileUpdateRequest,
    SignUpValidationRequest,
    SignUpValidationResponse,
    UsernameAvailabilityResponse,
)
from app.data.supabase_client import supabase_client

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{3,19}$")
PHONE_DIGIT_PATTERN = re.compile(r"^\d{9,15}$")
FULL_NAME_PATTERN = re.compile(r"^[A-Za-z가-힣\s]{2,40}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_SYMBOL_PATTERN = re.compile(r"[^A-Za-z0-9]")


def normalize_username(username: str) -> str:
    return username.strip().lower()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(username.strip()))


def is_valid_email(email: str | None) -> bool:
    normalized = normalize_email(email or "")
    return bool(normalized and EMAIL_PATTERN.fullmatch(normalized))


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


def describe_password_rule_failure(password: str, password_confirm: str) -> str | None:
    if len(password) < 10:
        return "비밀번호는 10자 이상이어야 합니다."
    if not re.search(r"[A-Z]", password):
        return "비밀번호에 영문 대문자를 포함해 주세요."
    if not re.search(r"[a-z]", password):
        return "비밀번호에 영문 소문자를 포함해 주세요."
    if not re.search(r"\d", password):
        return "비밀번호에 숫자를 포함해 주세요."
    if not PASSWORD_SYMBOL_PATTERN.search(password):
        return "비밀번호에 특수문자를 포함해 주세요."
    if password != password_confirm:
        return "비밀번호 재확인이 일치하지 않습니다."
    return None


def build_account_profile(user: AuthenticatedUser) -> AccountProfile:
    return AccountProfile(
        user_id=user.id,
        email=user.email,
        pending_email=normalize_email(user.pending_email or "") or None,
        email_verified=user.email_verified,
        email_confirmed_at=user.email_confirmed_at,
        email_change_sent_at=user.email_change_sent_at,
        username=normalize_username(user.username or "") or None,
        full_name=(user.full_name or "").strip() or None,
        phone_number=format_phone_number(user.phone_number),
        phone_masked=mask_phone_number(user.phone_number),
        birth_date=user.birth_date,
    )


async def get_current_profile(user: AuthenticatedUser) -> AccountProfile:
    return build_account_profile(user)


def _require_valid_account_profile(payload: AccountProfileUpdateRequest) -> tuple[str, str, str, str]:
    normalized_username = normalize_username(payload.username)
    normalized_full_name = normalize_full_name(payload.full_name)
    normalized_phone_number = normalize_phone_number(payload.phone_number)
    birth_date = payload.birth_date.strip()

    if not is_valid_username(normalized_username):
        raise ApiAppException(
            400,
            SP_6015("아이디는 영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 4~20자까지 사용할 수 있습니다."),
        )
    if not is_valid_full_name(normalized_full_name):
        raise ApiAppException(400, SP_6015("이름은 2~40자의 한글, 영문, 공백만 사용할 수 있습니다."))
    if not is_valid_phone_number(normalized_phone_number):
        raise ApiAppException(400, SP_6015("전화번호는 숫자 기준 9~15자리로 입력해 주세요."))
    if not is_valid_birth_date(birth_date):
        raise ApiAppException(400, SP_6015("생년월일을 올바르게 입력해 주세요."))

    return (
        normalized_username,
        normalized_full_name or "",
        normalized_phone_number or "",
        birth_date,
    )


async def update_current_profile(
    user: AuthenticatedUser,
    payload: AccountProfileUpdateRequest,
) -> AccountProfile:
    normalized_username, normalized_full_name, normalized_phone_number, birth_date = _require_valid_account_profile(payload)

    availability = await check_username_availability(normalized_username, exclude_user_id=user.id)
    if not availability.available:
        raise ApiAppException(409, SP_6015("이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요."))

    await supabase_client.admin_update_user_metadata(
        user.id,
        {
            "username": normalized_username,
            "full_name": normalized_full_name,
            "phone_number": normalized_phone_number,
            "birth_date": birth_date,
        },
    )

    return build_account_profile(
        AuthenticatedUser(
            id=user.id,
            email=user.email,
            pending_email=user.pending_email,
            email_verified=user.email_verified,
            email_confirmed_at=user.email_confirmed_at,
            email_change_sent_at=user.email_change_sent_at,
            username=normalized_username,
            full_name=normalized_full_name,
            phone_number=normalized_phone_number,
            birth_date=birth_date,
        )
    )


async def validate_signup(payload: SignUpValidationRequest) -> SignUpValidationResponse:
    normalized_email = normalize_email(payload.email)
    if not is_valid_email(normalized_email):
        raise ApiAppException(400, SP_6015("이메일 형식을 올바르게 입력해 주세요."))

    normalized_username, normalized_full_name, normalized_phone_number, birth_date = _require_valid_account_profile(
        AccountProfileUpdateRequest(
            username=payload.username,
            full_name=payload.full_name,
            phone_number=payload.phone_number,
            birth_date=payload.birth_date,
        )
    )

    password_error = describe_password_rule_failure(payload.password, payload.password_confirm)
    if password_error:
        raise ApiAppException(400, SP_6015(password_error))

    availability = await check_username_availability(normalized_username)
    if not availability.available:
        raise ApiAppException(409, SP_6015("이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요."))

    return SignUpValidationResponse(
        email=normalized_email,
        normalized_username=normalized_username,
        normalized_full_name=normalized_full_name,
        normalized_phone_number=normalized_phone_number,
        birth_date=birth_date,
    )


async def delete_current_account(
    user: AuthenticatedUser,
    payload: AccountDeleteRequest,
) -> AccountDeleteResponse:
    expected_username = normalize_username(user.username or "")
    expected_email = normalize_email(user.email or "")
    confirmation_raw = payload.confirmation_text.strip()
    confirmation_username = normalize_username(confirmation_raw)
    confirmation_email = normalize_email(confirmation_raw)

    if expected_username:
        if confirmation_username != expected_username:
            raise ApiAppException(400, SP_6015("회원 탈퇴를 진행하려면 현재 아이디를 정확히 입력해 주세요."))
    elif expected_email:
        if confirmation_email != expected_email:
            raise ApiAppException(400, SP_6015("회원 탈퇴를 진행하려면 현재 이메일을 정확히 입력해 주세요."))
    else:
        raise ApiAppException(400, SP_6015("계정 확인 기준을 찾을 수 없습니다. 다시 로그인한 뒤 시도해 주세요."))

    await supabase_client.admin_delete_user(user.id)
    return AccountDeleteResponse()


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
