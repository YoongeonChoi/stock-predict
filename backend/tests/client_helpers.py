from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_current_user
from app.main import app, settings as app_settings


DEFAULT_AUTHENTICATED_USER = AuthenticatedUser(
    id="user-123",
    email="tester@example.com",
)


@contextmanager
def patched_client(
    *,
    authenticated: bool = False,
    user: AuthenticatedUser | None = None,
):
    async def _fake_current_user():
        return user or DEFAULT_AUTHENTICATED_USER

    if authenticated or user is not None:
        app.dependency_overrides[get_current_user] = _fake_current_user

    with (
        patch("app.main.db.initialize", new=AsyncMock()),
        patch.object(app_settings, "startup_prediction_accuracy_refresh", False),
        patch.object(app_settings, "startup_research_archive_sync", False),
        patch.object(app_settings, "startup_market_opportunity_prewarm", False),
    ):
        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)
