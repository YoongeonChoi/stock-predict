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

    def test_diagnostics_route_supports_legacy_and_system_paths(self):
        payload = {"status": "ok", "version": "2.52.10"}

        with patch(
            "app.routers.system.system_service.get_diagnostics",
            new=AsyncMock(return_value=payload),
        ):
            with patched_client() as client:
                legacy = client.get("/api/diagnostics")
                namespaced = client.get("/api/system/diagnostics")

        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(namespaced.status_code, 200)
        self.assertEqual(legacy.json(), payload)
        self.assertEqual(namespaced.json(), payload)

    def test_diagnostics_event_supports_additive_failure_metadata_on_both_paths(self):
        event_payload = {
            "route": "/portfolio",
            "event": "panel_degraded",
            "status": "degraded",
            "panel": "recommendation",
            "panel_key": "conditional_recommendation",
            "detail": "conditional recommendation timed out",
            "failure_class": "panel_fetch_failed",
            "operation_kind": "auth-read",
            "dependency_key": "supabase",
            "recovered": True,
            "timeout_ms": 3200,
            "occurred_at": "2026-04-03T11:00:00Z",
        }

        with patch("app.routers.system.route_stability_service.record_frontend_event") as record_event:
            with patched_client() as client:
                legacy = client.post("/api/diagnostics/event", json=event_payload)
                namespaced = client.post("/api/system/diagnostics/event", json=event_payload)

        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(namespaced.status_code, 200)
        self.assertEqual(legacy.json(), {"status": "ok"})
        self.assertEqual(namespaced.json(), {"status": "ok"})
        self.assertEqual(record_event.call_count, 2)

        first_call = record_event.call_args_list[0].kwargs
        second_call = record_event.call_args_list[1].kwargs
        for forwarded in (first_call, second_call):
            self.assertEqual(forwarded["route"], event_payload["route"])
            self.assertEqual(forwarded["event"], event_payload["event"])
            self.assertEqual(forwarded["status"], event_payload["status"])
            self.assertEqual(forwarded["panel"], event_payload["panel"])
            self.assertEqual(forwarded["panel_key"], event_payload["panel_key"])
            self.assertEqual(forwarded["detail"], event_payload["detail"])
            self.assertEqual(forwarded["failure_class"], event_payload["failure_class"])
            self.assertEqual(forwarded["operation_kind"], event_payload["operation_kind"])
            self.assertEqual(forwarded["dependency_key"], event_payload["dependency_key"])
            self.assertEqual(forwarded["recovered"], event_payload["recovered"])
            self.assertEqual(forwarded["timeout_ms"], event_payload["timeout_ms"])
            self.assertEqual(forwarded["occurred_at"], event_payload["occurred_at"])

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
