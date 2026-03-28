import unittest
from unittest.mock import AsyncMock, patch

from app.services.public_rate_limit_service import reset_public_rate_limit_state
from client_helpers import patched_client


class ApiErrorContractTests(unittest.TestCase):
    def setUp(self):
        reset_public_rate_limit_state()

    def tearDown(self):
        reset_public_rate_limit_state()

    def test_portfolio_validation_error_returns_structured_error_code(self):
        with patched_client(authenticated=True) as client:
            response = client.post("/api/portfolio/holdings", json={"ticker": "AAPL"})

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6009")
        self.assertIn("message", body)

    def test_unknown_api_route_returns_structured_not_found_code(self):
        with patched_client() as client:
            response = client.get("/api/does-not-exist")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6011")

    def test_wrong_method_returns_structured_method_not_allowed_code(self):
        with patched_client() as client:
            response = client.post("/api/countries")

        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6012")

    def test_research_predictions_route_exists(self):
        with (
            patch(
                "app.routers.research.research_service.get_prediction_lab",
                new=AsyncMock(return_value={"generated_at": "2026-03-24T00:00:00", "accuracy": {}, "breakdown": {}, "calibration": [], "recent_trend": [], "recent_records": [], "insights": []}),
            ),
        ):
            with patched_client() as client:
                response = client.get("/api/research/predictions?limit_recent=20&refresh=false")

        self.assertEqual(response.status_code, 200)
        self.assertIn("generated_at", response.json())

    def test_public_account_rate_limit_returns_structured_error_code(self):
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
                response = client.get("/api/account/username-availability?username=alpha_01")

        self.assertEqual(response.status_code, 429)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6016")
        self.assertEqual(body["message"], "Too many public account requests")
        retry_after = response.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreaterEqual(int(retry_after), 1)


if __name__ == "__main__":
    unittest.main()
