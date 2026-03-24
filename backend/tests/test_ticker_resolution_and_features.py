import asyncio
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import ticker_resolver_service, forecast_monitor_service


@contextmanager
def patched_client():
    with (
        patch("app.main.db.initialize", new=AsyncMock()),
        patch("app.main.archive_service.refresh_prediction_accuracy", new=AsyncMock(return_value=None)),
        patch("app.main.research_archive_service.sync_public_research_reports", new=AsyncMock(return_value={"processed_total": 0})),
    ):
        with TestClient(app) as client:
            yield client


class TickerResolutionAndFeatureTests(unittest.TestCase):
    def test_resolve_ticker_normalizes_kr_and_jp_numeric_codes(self):
        kr = ticker_resolver_service.resolve_ticker("005930", "KR")
        jp = ticker_resolver_service.resolve_ticker("8001", "JP")

        self.assertEqual(kr["ticker"], "005930.KS")
        self.assertEqual(kr["country_code"], "KR")
        self.assertEqual(jp["ticker"], "8001.T")
        self.assertEqual(jp["country_code"], "JP")

    def test_ticker_resolve_route_returns_structured_resolution(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch("app.main.archive_service.refresh_prediction_accuracy", new=AsyncMock(return_value=None)),
            patch("app.main.research_archive_service.sync_public_research_reports", new=AsyncMock(return_value={"processed_total": 0})),
            patch("app.routers.stock.yfinance_client.get_stock_info", new=AsyncMock(return_value={"name": "Itochu Corp"})),
        ):
            with TestClient(app) as client:
                response = client.get("/api/ticker/resolve?query=8001&country_code=JP")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ticker"], "8001.T")
        self.assertEqual(body["country_code"], "JP")
        self.assertEqual(body["name"], "Itochu Corp")

    def test_daily_briefing_and_portfolio_event_routes_exist(self):
        with (
            patch("app.main.db.initialize", new=AsyncMock()),
            patch("app.main.archive_service.refresh_prediction_accuracy", new=AsyncMock(return_value=None)),
            patch("app.main.research_archive_service.sync_public_research_reports", new=AsyncMock(return_value={"processed_total": 0})),
            patch(
                "app.routers.briefing.briefing_service.get_daily_briefing",
                new=AsyncMock(return_value={"generated_at": "2026-03-24T00:00:00", "sessions": [], "market_view": [], "focus_cards": [], "upcoming_events": [], "research_archive": {}, "priorities": []}),
            ),
            patch(
                "app.routers.portfolio.portfolio_event_service.get_portfolio_event_radar",
                new=AsyncMock(return_value={"generated_at": "2026-03-24T00:00:00", "window_days": 14, "events": []}),
            ),
        ):
            with TestClient(app) as client:
                briefing = client.get("/api/briefing/daily")
                event_radar = client.get("/api/portfolio/event-radar?days=14")

        self.assertEqual(briefing.status_code, 200)
        self.assertEqual(event_radar.status_code, 200)
        self.assertIn("generated_at", briefing.json())
        self.assertIn("events", event_radar.json())

    def test_forecast_monitor_builds_delta_summary(self):
        rows = [
            {
                "target_date": "2026-03-25",
                "reference_date": "2026-03-24",
                "reference_price": 100.0,
                "predicted_close": 103.0,
                "predicted_low": 99.0,
                "predicted_high": 105.0,
                "up_probability": 61.0,
                "confidence": 68.0,
                "direction": "up",
                "actual_close": None,
                "model_version": "signal-v2.4",
                "created_at": 2,
            },
            {
                "target_date": "2026-03-24",
                "reference_date": "2026-03-23",
                "reference_price": 98.0,
                "predicted_close": 100.0,
                "predicted_low": 96.0,
                "predicted_high": 102.0,
                "up_probability": 55.0,
                "confidence": 63.0,
                "direction": "up",
                "actual_close": 101.0,
                "model_version": "signal-v2.4",
                "created_at": 1,
            },
        ]

        with patch("app.services.forecast_monitor_service.db.prediction_symbol_history", new=AsyncMock(return_value=rows)):
            result = asyncio.run(forecast_monitor_service.get_stock_forecast_delta("AAPL", limit=5))

        self.assertTrue(result["summary"]["available"])
        self.assertAlmostEqual(result["summary"]["up_probability_delta"], 6.0)
        self.assertEqual(result["history"][0]["direction_label"], "상승")


if __name__ == "__main__":
    unittest.main()

