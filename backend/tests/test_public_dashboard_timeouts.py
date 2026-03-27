import asyncio
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


async def _slow_response(*args, **kwargs):
    await asyncio.sleep(0.05)
    return {}


async def _return_fetcher(key, fetcher, ttl=None):
    return await fetcher()


class PublicDashboardTimeoutTests(unittest.TestCase):
    def test_country_report_timeout_returns_structured_error(self):
        with (
            patch("app.routers.country.PUBLIC_ENDPOINT_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.analyze_country", new=AsyncMock(side_effect=_slow_response)),
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/report")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error_code"], "SP-5018")

    def test_market_opportunities_timeout_returns_structured_error(self):
        with (
            patch("app.routers.country.OPPORTUNITY_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=_slow_response)),
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error_code"], "SP-5018")

    def test_heatmap_timeout_returns_partial_fallback(self):
        with (
            patch("app.routers.country.HEATMAP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country._build_heatmap_payload", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country._build_heatmap_fallback", new=AsyncMock(return_value={"children": [], "partial": True})),
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/heatmap")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])

    def test_daily_briefing_timeout_returns_structured_error(self):
        with (
            patch("app.routers.briefing.PUBLIC_ENDPOINT_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.briefing.briefing_service.get_daily_briefing", new=AsyncMock(side_effect=_slow_response)),
            patched_client() as client,
        ):
            response = client.get("/api/briefing/daily")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error_code"], "SP-5018")

    def test_screener_timeout_returns_snapshot_fallback(self):
        async def _slow_gather(*args, **kwargs):
            await asyncio.sleep(0.05)
            return []

        with (
            patch("app.routers.screener.PUBLIC_SCREENER_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.screener.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value={"Information Technology": ["005930.KS"]})),
            patch("app.routers.screener.gather_limited", new=AsyncMock(side_effect=_slow_gather)),
            patch("app.routers.screener.yfinance_client.get_market_snapshot", new=AsyncMock(return_value={"valid": True, "current_price": 70000.0, "market_cap": 420000000000.0, "change_pct": 1.5, "name": "Samsung Electronics"})),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])


if __name__ == "__main__":
    unittest.main()
