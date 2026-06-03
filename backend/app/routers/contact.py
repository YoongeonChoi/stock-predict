from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.errors import AppError, SP_5020
from app.exceptions import ApiAppException
from app.models.contact import ContactSubmissionRequest
from app.services import contact_service

router = APIRouter(prefix="/api", tags=["contact"])
log = logging.getLogger("stock_predict.contact.router")


def _contact_error_response(
    status_code: int,
    error: AppError,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = error.to_dict()
    user_message = error.detail or error.message
    payload.update({"ok": False, "error": user_message})
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


@router.post("/contact")
async def post_contact(request: Request, payload: ContactSubmissionRequest):
    try:
        return await contact_service.submit_contact_message(request, payload)
    except ApiAppException as exc:
        exc.error.log("warning" if exc.status_code < 500 else "error")
        return _contact_error_response(exc.status_code, exc.error, headers=exc.headers)
    except Exception as exc:
        log.error("Unhandled contact submission error: %s", exc, exc_info=True)
        error = SP_5020("문의 저장 설정을 확인한 뒤 다시 시도해 주세요.")
        return _contact_error_response(500, error)
