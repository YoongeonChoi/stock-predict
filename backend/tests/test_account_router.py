import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_current_user
from app.main import app


@contextmanager
def patched_client():
    with (
        patch("app.main.db.initialize", new=AsyncMock()),
        patch("app.main.archive_service.refresh_prediction_accuracy", new=AsyncMock(return_value=None)),
        patch("app.main.research_archive_service.sync_public_research_reports", new=AsyncMock(return_value={"processed_total": 0})),
    ):
        with TestClient(app) as client:
            yield client


class AccountRouterTests(unittest.TestCase):
    def test_signup_validation_route_is_public(self):
        with patch(
            "app.routers.account.account_service.validate_signup",
            new=AsyncMock(
                return_value={
                    "email": "tester@example.com",
                    "normalized_username": "beta_02",
                    "normalized_full_name": "김 가은",
                    "normalized_phone_number": "01077778888",
                    "birth_date": "1997-08-11",
                    "ready": True,
                    "message": "회원가입 조건이 확인되었습니다.",
                }
            ),
        ):
            with patched_client() as client:
                response = client.post(
                    "/api/account/signup/validate",
                    json={
                        "username": "beta_02",
                        "email": "tester@example.com",
                        "full_name": "김 가은",
                        "phone_number": "010-7777-8888",
                        "birth_date": "1997-08-11",
                        "password": "Secure!234A",
                        "password_confirm": "Secure!234A",
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ready"])
        self.assertEqual(body["normalized_username"], "beta_02")

    def test_username_availability_route_is_public(self):
        with patch(
            "app.routers.account.account_service.check_username_availability",
            new=AsyncMock(
                return_value={
                    "username": "alpha_01",
                    "normalized_username": "alpha_01",
                    "valid": True,
                    "available": True,
                    "message": "사용 가능한 아이디입니다.",
                }
            ),
        ):
            with patched_client() as client:
                response = client.get("/api/account/username-availability?username=alpha_01")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["available"])
        self.assertEqual(body["normalized_username"], "alpha_01")

    def test_account_profile_update_route_returns_updated_profile(self):
        async def override_user():
            return AuthenticatedUser(
                id="user-123",
                email="tester@example.com",
                email_verified=True,
                email_confirmed_at="2026-03-27T10:00:00Z",
                username="alpha_01",
                full_name="홍 길동",
                phone_number="01012345678",
                birth_date="1998-03-14",
            )

        app.dependency_overrides[get_current_user] = override_user
        try:
            with patch(
                "app.routers.account.account_service.update_current_profile",
                new=AsyncMock(
                    return_value={
                        "user_id": "user-123",
                        "email": "tester@example.com",
                        "email_verified": True,
                        "email_confirmed_at": "2026-03-27T10:00:00Z",
                        "username": "beta_02",
                        "full_name": "김 가은",
                        "phone_number": "010-7777-8888",
                        "phone_masked": "010-****-8888",
                        "birth_date": "1997-08-11",
                    }
                ),
            ):
                with patched_client() as client:
                    response = client.patch(
                        "/api/account/me",
                        json={
                            "username": "beta_02",
                            "full_name": "김 가은",
                            "phone_number": "010-7777-8888",
                            "birth_date": "1997-08-11",
                        },
                    )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "beta_02")
        self.assertTrue(body["email_verified"])


if __name__ == "__main__":
    unittest.main()
