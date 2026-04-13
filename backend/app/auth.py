from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from fastapi import Header

from app.data.supabase_client import SupabaseConfigError, supabase_client
from app.errors import SP_1006, SP_5001, SP_6014
from app.exceptions import ApiAppException


class SupabaseUserDict(TypedDict, total=False):
    id: str
    email: str | None
    new_email: str | None
    email_confirmed_at: str | None
    confirmed_at: str | None
    email_change_sent_at: str | None
    user_metadata: dict
    raw_user_meta_data: dict


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None
    pending_email: str | None = None
    email_verified: bool = False
    email_confirmed_at: str | None = None
    email_change_sent_at: str | None = None
    username: str | None = None
    full_name: str | None = None
    phone_number: str | None = None
    birth_date: str | None = None


def _extract_profile_fields(user: SupabaseUserDict) -> dict[str, str | None]:
    metadata = user.get("user_metadata")
    if not isinstance(metadata, dict):
        metadata = user.get("raw_user_meta_data")
    if not isinstance(metadata, dict):
        metadata = {}

    def read_text(*keys: str) -> str | None:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    username = read_text("username")
    return {
        "username": username.lower() if username else None,
        "full_name": read_text("full_name", "name"),
        "phone_number": read_text("phone_number", "phone"),
        "birth_date": read_text("birth_date"),
    }


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.strip().lower() != "bearer":
        return None
    token = token.strip()
    return token or None


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization)
    if not token:
        err = SP_6014()
        err.log("warning")
        raise ApiAppException(401, err)

    try:
        user = await supabase_client.get_user(token)
    except SupabaseConfigError:
        err = SP_1006()
        err.log()
        raise ApiAppException(500, err)
    except Exception as exc:
        err = SP_5001(f"supabase auth lookup failed: {str(exc)[:200]}")
        err.log()
        raise ApiAppException(500, err)

    if user is None or not user.get("id"):
        err = SP_6014()
        err.log("warning")
        raise ApiAppException(401, err)

    profile = _extract_profile_fields(user)
    email_confirmed_at = user.get("email_confirmed_at") or user.get("confirmed_at")
    return AuthenticatedUser(
        id=str(user["id"]),
        email=user.get("email"),
        pending_email=user.get("new_email"),
        email_verified=bool(email_confirmed_at),
        email_confirmed_at=str(email_confirmed_at) if email_confirmed_at else None,
        email_change_sent_at=str(user.get("email_change_sent_at")) if user.get("email_change_sent_at") else None,
        username=profile["username"],
        full_name=profile["full_name"],
        phone_number=profile["phone_number"],
        birth_date=profile["birth_date"],
    )
