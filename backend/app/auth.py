from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from app.data.supabase_client import SupabaseConfigError, supabase_client
from app.errors import SP_1006, SP_5001, SP_6014
from app.exceptions import ApiAppException


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str | None = None


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

    return AuthenticatedUser(id=str(user["id"]), email=user.get("email"))
