import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
