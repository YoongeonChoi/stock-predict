from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request

from app.config import get_settings
from app.data.supabase_client import supabase_client
from app.errors import SP_5020, SP_6018
from app.exceptions import ApiAppException
from app.models.contact import ContactSubmissionRequest, ContactSubmissionResponse
from app.services import contact_notifier, public_rate_limit_service

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SUCCESS_MESSAGE = "문의가 정상적으로 접수되었습니다."
log = logging.getLogger("stock_predict.contact")


@dataclass(frozen=True)
class ValidatedContactSubmission:
    name: str
    email: str
    subject: str
    message: str


def _compact_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_contact_email(value: str) -> str:
    return value.strip().lower()


def _field_subject(field_label: str) -> str:
    if field_label == "메시지":
        return "메시지는"
    return f"{field_label}은"


def _require_length(value: str, *, field_label: str, minimum: int, maximum: int) -> None:
    field_subject = _field_subject(field_label)
    length = len(value)
    if length < minimum:
        raise ApiAppException(400, SP_6018(f"{field_subject} 최소 {minimum}자 이상 입력해야 합니다."))
    if length > maximum:
        raise ApiAppException(400, SP_6018(f"{field_subject} 최대 {maximum}자까지 입력할 수 있습니다."))


def validate_contact_submission(payload: ContactSubmissionRequest) -> ValidatedContactSubmission:
    if payload.company.strip():
        raise ApiAppException(400, SP_6018("문의 제출 형식이 올바르지 않습니다."))

    name = _compact_spaces(payload.name)
    email = normalize_contact_email(payload.email)
    subject = _compact_spaces(payload.subject)
    message = payload.message.strip()

    _require_length(name, field_label="이름", minimum=1, maximum=80)
    _require_length(email, field_label="이메일", minimum=1, maximum=120)
    if not EMAIL_PATTERN.fullmatch(email):
        raise ApiAppException(400, SP_6018("이메일 형식을 올바르게 입력해 주세요."))
    _require_length(subject, field_label="제목", minimum=1, maximum=120)
    _require_length(message, field_label="메시지", minimum=10, maximum=3000)

    return ValidatedContactSubmission(
        name=name,
        email=email,
        subject=subject,
        message=message,
    )


def _hash_client_identifier(client_identifier: str) -> str | None:
    salt = get_settings().contact_ip_hash_salt.strip()
    normalized = client_identifier.strip()
    if not salt or not normalized or normalized == "unknown":
        return None
    return hashlib.sha256(f"{salt}:{normalized}".encode("utf-8")).hexdigest()


def _request_user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "").strip()[:300]


def _storage_payload(request: Request, submission: ValidatedContactSubmission) -> dict[str, str | None]:
    client_identifier = public_rate_limit_service.get_request_client_identifier(request)
    return {
        "name": submission.name,
        "email": submission.email,
        "subject": submission.subject,
        "message": submission.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": _request_user_agent(request) or None,
        "ip_hash": _hash_client_identifier(client_identifier),
        "status": "received",
    }


async def submit_contact_message(
    request: Request,
    payload: ContactSubmissionRequest,
) -> ContactSubmissionResponse:
    submission = validate_contact_submission(payload)
    public_rate_limit_service.enforce_public_contact_rate_limit(request, submission.email)
    storage_payload = _storage_payload(request, submission)

    try:
        saved_message = await supabase_client.contact_message_insert(storage_payload)
    except Exception as exc:
        log.warning("Contact message save failed: %s", exc, exc_info=True)
        raise ApiAppException(
            500,
            SP_5020("문의 저장 설정을 확인한 뒤 다시 시도해 주세요."),
        ) from exc

    try:
        await contact_notifier.notify_contact_received(saved_message or storage_payload)
    except Exception as exc:  # pragma: no cover - future provider is best-effort
        log.warning("Contact notification hook failed: %s", exc, exc_info=True)

    return ContactSubmissionResponse(ok=True, message=SUCCESS_MESSAGE)
