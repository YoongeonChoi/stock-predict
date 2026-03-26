from __future__ import annotations

from app.errors import AppError


class ApiAppException(Exception):
    def __init__(self, status_code: int, error: AppError):
        super().__init__(error.message)
        self.status_code = status_code
        self.error = error
