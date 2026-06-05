import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.exceptions import ApiAppException
from app.models.investment_profile import InvestmentProfileUpdateRequest
from app.services import investment_profile_service


class InvestmentProfileServiceTests(unittest.TestCase):
    def test_get_profile_returns_default_balanced_when_not_saved(self):
        with patch(
            "app.services.investment_profile_service.supabase_client.investment_profile_get",
            new=AsyncMock(return_value=None),
        ):
            profile = asyncio.run(investment_profile_service.get_investment_profile("user-123"))

        self.assertEqual(profile.profile_code, "balanced")
        self.assertEqual(profile.profile_label, "균형형")
        self.assertFalse(profile.persisted)

    def test_update_profile_fills_defaults_and_persists_by_user(self):
        async def _upsert(user_id, payload):
            return {"user_id": user_id, **payload, "created_at": "2026-06-05T00:00:00Z"}

        with patch(
            "app.services.investment_profile_service.supabase_client.investment_profile_upsert",
            new=AsyncMock(side_effect=_upsert),
        ) as upsert:
            profile = asyncio.run(
                investment_profile_service.update_investment_profile(
                    "user-123",
                    InvestmentProfileUpdateRequest(profile_code="growth"),
                )
            )

        upsert.assert_awaited_once()
        saved_payload = upsert.await_args.args[1]
        self.assertEqual(profile.profile_code, "growth")
        self.assertEqual(profile.profile_label, "성장추구형")
        self.assertEqual(saved_payload["policy_version"], "investment-policy-v1")
        self.assertEqual(saved_payload["risk_tolerance"], 4)
        self.assertEqual(saved_payload["investment_horizon"], "long")
        self.assertTrue(profile.persisted)

    def test_update_profile_rejects_unknown_code(self):
        with self.assertRaises(ApiAppException) as ctx:
            asyncio.run(
                investment_profile_service.update_investment_profile(
                    "user-123",
                    InvestmentProfileUpdateRequest(profile_code="very-fast"),
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error.code, "SP-6020")


if __name__ == "__main__":
    unittest.main()
