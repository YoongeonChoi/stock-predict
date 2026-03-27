import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.auth import AuthenticatedUser
from app.exceptions import ApiAppException
from app.models.account import AccountProfileUpdateRequest
from app.services import account_service


class AccountServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_username_validation_rules(self):
        self.assertTrue(account_service.is_valid_username("alpha_01"))
        self.assertFalse(account_service.is_valid_username("1alpha"))
        self.assertFalse(account_service.is_valid_username("ab"))
        self.assertFalse(account_service.is_valid_username("ALPHA"))

    def test_full_name_phone_and_birth_date_validation(self):
        self.assertTrue(account_service.is_valid_full_name("홍 길동"))
        self.assertTrue(account_service.is_valid_phone_number("010-1234-5678"))
        self.assertTrue(account_service.is_valid_birth_date("1998-03-14"))
        self.assertFalse(account_service.is_valid_full_name("A"))
        self.assertFalse(account_service.is_valid_phone_number("010-12"))
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertFalse(account_service.is_valid_birth_date(tomorrow))

    def test_build_account_profile_masks_phone(self):
        profile = account_service.build_account_profile(
            AuthenticatedUser(
                id="user-123",
                email="tester@example.com",
                username="Alpha_01",
                full_name="홍 길동",
                phone_number="01012345678",
                birth_date="1998-03-14",
            )
        )

        self.assertEqual(profile.username, "alpha_01")
        self.assertEqual(profile.phone_number, "010-1234-5678")
        self.assertEqual(profile.phone_masked, "010-****-5678")

    async def test_username_availability_uses_supabase_lookup(self):
        with patch(
            "app.services.account_service.supabase_client.find_user_by_username",
            new=AsyncMock(return_value={"id": "user-777"}),
        ):
            taken = await account_service.check_username_availability("alpha_01")

        self.assertTrue(taken.valid)
        self.assertFalse(taken.available)
        self.assertEqual(taken.normalized_username, "alpha_01")

        with patch(
            "app.services.account_service.supabase_client.find_user_by_username",
            new=AsyncMock(return_value=None),
        ):
            available = await account_service.check_username_availability("beta_02")

        self.assertTrue(available.available)
        self.assertIn("사용 가능", available.message)

    async def test_update_current_profile_updates_metadata(self):
        user = AuthenticatedUser(
            id="user-123",
            email="tester@example.com",
            email_verified=True,
            email_confirmed_at="2026-03-27T10:00:00Z",
            username="alpha_01",
            full_name="홍 길동",
            phone_number="01012345678",
            birth_date="1998-03-14",
        )
        payload = AccountProfileUpdateRequest(
            username="beta_02",
            full_name="김 가은",
            phone_number="010-7777-8888",
            birth_date="1997-08-11",
        )

        with (
            patch(
                "app.services.account_service.supabase_client.find_user_by_username",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.account_service.supabase_client.admin_update_user_metadata",
                new=AsyncMock(return_value={"id": "user-123"}),
            ) as mocked_update,
        ):
            profile = await account_service.update_current_profile(user, payload)

        mocked_update.assert_awaited_once_with(
            "user-123",
            {
                "username": "beta_02",
                "full_name": "김 가은",
                "phone_number": "01077778888",
                "birth_date": "1997-08-11",
            },
        )
        self.assertEqual(profile.username, "beta_02")
        self.assertEqual(profile.phone_number, "010-7777-8888")
        self.assertTrue(profile.email_verified)

    async def test_update_current_profile_rejects_duplicate_username(self):
        user = AuthenticatedUser(id="user-123", email="tester@example.com")
        payload = AccountProfileUpdateRequest(
            username="alpha_01",
            full_name="홍 길동",
            phone_number="010-1234-5678",
            birth_date="1998-03-14",
        )

        with patch(
            "app.services.account_service.supabase_client.find_user_by_username",
            new=AsyncMock(return_value={"id": "user-777"}),
        ):
            with self.assertRaises(ApiAppException) as ctx:
                await account_service.update_current_profile(user, payload)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.error.to_dict()["error_code"], "SP-6015")


if __name__ == "__main__":
    unittest.main()
