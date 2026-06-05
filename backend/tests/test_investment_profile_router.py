import unittest
from unittest.mock import AsyncMock, patch

from client_helpers import patched_client


PROFILE_PAYLOAD = {
    "profile_code": "balanced",
    "profile_label": "균형형",
    "risk_tolerance": 3,
    "investment_horizon": "medium",
    "max_drawdown_pct": 15.0,
    "turnover_preference": "medium",
    "concentration_preference": "medium",
    "cash_buffer_min_pct": 10.0,
    "cash_buffer_max_pct": 25.0,
    "policy_version": "investment-policy-v1",
    "questionnaire_json": {},
    "updated_at": None,
    "persisted": False,
}


class InvestmentProfileRouterTests(unittest.TestCase):
    def test_investment_profile_routes_return_contract(self):
        with (
            patch(
                "app.routers.investment_profile.investment_profile_service.get_investment_profile",
                new=AsyncMock(return_value=PROFILE_PAYLOAD),
            ),
            patch(
                "app.routers.investment_profile.investment_profile_service.update_investment_profile",
                new=AsyncMock(return_value={**PROFILE_PAYLOAD, "profile_code": "growth", "profile_label": "성장추구형", "persisted": True}),
            ),
        ):
            with patched_client(authenticated=True) as client:
                get_response = client.get("/api/investment-profile")
                put_response = client.put("/api/investment-profile", json={"profile_code": "growth"})

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(get_response.json()["profile_code"], "balanced")
        self.assertEqual(put_response.json()["profile_code"], "growth")
        self.assertTrue(put_response.json()["persisted"])

    def test_investment_profile_options_and_personalized_route_exist(self):
        options_payload = {
            "policy_version": "investment-policy-v1",
            "options": [
                {
                    "profile_code": "balanced",
                    "profile_label": "균형형",
                    "description": "수익과 리스크를 균형 있게 반영합니다.",
                    "risk_tolerance": 3,
                    "recommended_equity_pct": 82.0,
                    "cash_buffer_pct": 18.0,
                    "max_single_weight_pct": 14.5,
                    "optimization_style": "balanced",
                }
            ],
        }
        personalized_payload = {
            "generated_at": "2026-06-05T00:00:00",
            "objective": "personalized",
            "style": "balanced",
            "budget": {
                "style": "balanced",
                "style_label": "균형형",
                "recommended_equity_pct": 82.0,
                "cash_buffer_pct": 18.0,
                "target_position_count": 7,
                "max_single_weight_pct": 14.5,
                "max_country_weight_pct": 48.0,
                "max_sector_weight_pct": 28.0,
            },
            "recommendation_policy": None,
            "summary": {},
            "recommendations": [],
            "notes": [],
            "market_view": [],
        }
        with (
            patch(
                "app.routers.investment_profile.investment_profile_service.get_investment_profile_options",
                return_value=options_payload,
            ),
            patch(
                "app.routers.portfolio.portfolio_recommendation_service.get_personalized_recommendation",
                new=AsyncMock(return_value=personalized_payload),
            ),
        ):
            with patched_client(authenticated=True) as client:
                options_response = client.get("/api/investment-profile/options")
                personalized_response = client.get("/api/portfolio/recommendations/personalized")

        self.assertEqual(options_response.status_code, 200)
        self.assertEqual(personalized_response.status_code, 200)
        self.assertEqual(options_response.json()["options"][0]["profile_code"], "balanced")
        self.assertIn("recommendations", personalized_response.json())


if __name__ == "__main__":
    unittest.main()
