import unittest
from unittest.mock import AsyncMock, patch

from app.auth import AuthenticatedUser
from app.services.public_rate_limit_service import reset_public_rate_limit_state
from client_helpers import patched_client


class AccountRouterTests(unittest.TestCase):
    def setUp(self):
        reset_public_rate_limit_state()

    def tearDown(self):
        reset_public_rate_limit_state()

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

    def test_username_availability_route_rate_limits_repeated_requests(self):
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
                for _ in range(12):
                    response = client.get("/api/account/username-availability?username=alpha_01")
                    self.assertEqual(response.status_code, 200)

                blocked = client.get("/api/account/username-availability?username=alpha_01")

        self.assertEqual(blocked.status_code, 429)
        body = blocked.json()
        self.assertEqual(body["error_code"], "SP-6016")
        self.assertIn("다시 시도", body["detail"])

    def test_signup_validation_route_rate_limits_repeated_requests(self):
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
                payload = {
                    "username": "beta_02",
                    "email": "tester@example.com",
                    "full_name": "김 가은",
                    "phone_number": "010-7777-8888",
                    "birth_date": "1997-08-11",
                    "password": "Secure!234A",
                    "password_confirm": "Secure!234A",
                }
                for _ in range(6):
                    response = client.post("/api/account/signup/validate", json=payload)
                    self.assertEqual(response.status_code, 200)

                blocked = client.post("/api/account/signup/validate", json=payload)

        self.assertEqual(blocked.status_code, 429)
        body = blocked.json()
        self.assertEqual(body["error_code"], "SP-6016")
        self.assertIn("회원가입 검증", body["detail"])

    def test_account_profile_update_route_returns_updated_profile(self):
        current_user = AuthenticatedUser(
            id="user-123",
            email="tester@example.com",
            email_verified=True,
            email_confirmed_at="2026-03-27T10:00:00Z",
            username="alpha_01",
            full_name="홍 길동",
            phone_number="01012345678",
            birth_date="1998-03-14",
        )

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
            with patched_client(user=current_user) as client:
                response = client.patch(
                    "/api/account/me",
                    json={
                        "username": "beta_02",
                        "full_name": "김 가은",
                        "phone_number": "010-7777-8888",
                        "birth_date": "1997-08-11",
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "beta_02")
        self.assertTrue(body["email_verified"])

    def test_account_delete_route_requires_confirmation(self):
        current_user = AuthenticatedUser(
            id="user-123",
            email="tester@example.com",
            username="alpha_01",
        )

        with patch(
            "app.routers.account.account_service.delete_current_account",
            new=AsyncMock(
                return_value={
                    "status": "deleted",
                    "message": "계정이 삭제되었습니다. 관심종목과 포트폴리오 데이터도 함께 정리되었습니다.",
                }
            ),
        ):
            with patched_client(user=current_user) as client:
                response = client.request(
                    "DELETE",
                    "/api/account/me",
                    json={"confirmation_text": "alpha_01"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "deleted")


if __name__ == "__main__":
    unittest.main()
