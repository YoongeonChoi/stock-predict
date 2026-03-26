import unittest
from unittest.mock import AsyncMock, patch

from app.auth import _extract_bearer_token, get_current_user
from app.data.supabase_client import SupabaseConfigError
from app.exceptions import ApiAppException


class AuthDependencyTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_bearer_token(self):
        self.assertEqual(_extract_bearer_token("Bearer abc"), "abc")
        self.assertIsNone(_extract_bearer_token("Basic abc"))
        self.assertIsNone(_extract_bearer_token(None))

    async def test_missing_authorization_raises_401(self):
        with self.assertRaises(ApiAppException) as ctx:
            await get_current_user(None)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.error.to_dict()["error_code"], "SP-6014")

    async def test_supabase_config_error_becomes_500(self):
        with patch("app.auth.supabase_client.get_user", new=AsyncMock(side_effect=SupabaseConfigError("missing"))):
            with self.assertRaises(ApiAppException) as ctx:
                await get_current_user("Bearer token")

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.error.to_dict()["error_code"], "SP-1006")

    async def test_valid_user_returns_authenticated_user(self):
        with patch(
            "app.auth.supabase_client.get_user",
            new=AsyncMock(
                return_value={
                    "id": "user-123",
                    "email": "user@example.com",
                    "user_metadata": {
                        "username": "alpha_user",
                        "full_name": "홍 길동",
                        "phone_number": "01012345678",
                        "birth_date": "1999-01-31",
                    },
                }
            ),
        ):
            user = await get_current_user("Bearer token")

        self.assertEqual(user.id, "user-123")
        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(user.username, "alpha_user")
        self.assertEqual(user.full_name, "홍 길동")
        self.assertEqual(user.phone_number, "01012345678")
        self.assertEqual(user.birth_date, "1999-01-31")

    async def test_invalid_token_raises_401(self):
        with patch("app.auth.supabase_client.get_user", new=AsyncMock(return_value=None)):
            with self.assertRaises(ApiAppException) as ctx:
                await get_current_user("Bearer invalid")

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.error.to_dict()["error_code"], "SP-6014")


if __name__ == "__main__":
    unittest.main()
