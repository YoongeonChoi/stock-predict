import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from client_helpers import patched_client
from app.services import ticker_resolver_service, forecast_monitor_service


class TickerResolutionAndFeatureTests(unittest.TestCase):
    def test_resolve_ticker_normalizes_kr_numeric_codes(self):
        kr = ticker_resolver_service.resolve_ticker("005930", "KR")
        kr_prefixed = ticker_resolver_service.resolve_ticker("KRX:000660", "KR")

        self.assertEqual(kr["ticker"], "005930.KS")
        self.assertEqual(kr["country_code"], "KR")
        self.assertEqual(kr_prefixed["ticker"], "000660.KS")
        self.assertEqual(kr_prefixed["country_code"], "KR")

    def test_ticker_resolve_route_returns_structured_resolution(self):
        with patch("app.routers.stock.yfinance_client.get_stock_info", new=AsyncMock(return_value={"name": "Samsung Electronics"})):
            with patched_client() as client:
                response = client.get("/api/ticker/resolve?query=005930&country_code=KR")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ticker"], "005930.KS")
        self.assertEqual(body["country_code"], "KR")
        self.assertEqual(body["name"], "Samsung Electronics")

    def test_daily_briefing_and_portfolio_event_routes_exist(self):
        with (
            patch(
                "app.routers.briefing.briefing_service.get_daily_briefing",
                new=AsyncMock(return_value={"generated_at": "2026-03-24T00:00:00", "sessions": [], "market_view": [], "focus_cards": [], "upcoming_events": [], "research_archive": {}, "priorities": []}),
            ),
            patch(
                "app.routers.portfolio.portfolio_event_service.get_portfolio_event_radar",
                new=AsyncMock(return_value={"generated_at": "2026-03-24T00:00:00", "window_days": 14, "events": []}),
            ),
        ):
            with patched_client(authenticated=True) as client:
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
            result = asyncio.run(forecast_monitor_service.get_stock_forecast_delta("005930.KS", limit=5))

        self.assertTrue(result["summary"]["available"])
        self.assertAlmostEqual(result["summary"]["up_probability_delta"], 6.0)
        self.assertEqual(result["history"][0]["direction_label"], "상승")


if __name__ == "__main__":
    unittest.main()
