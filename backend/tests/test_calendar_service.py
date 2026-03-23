import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import calendar_service


class CalendarServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_calendar_returns_month_scoped_events(self):
        earning_rows = [
            {"date": "2026-03-18", "symbol": "AAPL", "time": "amc", "epsEstimated": 1.45},
            {"date": "2026-03-19", "symbol": "005930.KS", "time": "bmo", "epsEstimated": 2.1},
        ]
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "US"},
            {"date": "2026-03-25", "event": "GDP Report", "country": "United States"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=earning_rows)),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("US", year=2026, month=3)

        self.assertEqual(result["country_code"], "US")
        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["month"], 3)
        self.assertEqual(result["month_label"], "2026년 03월")
        self.assertGreater(result["summary"]["total_events"], 0)
        self.assertTrue(any(event["type"] == "earnings" for event in result["events"]))
        self.assertTrue(any(event["type"] in {"economic", "policy"} for event in result["events"]))
        self.assertTrue(all("description" in event for event in result["events"]))

    async def test_recurring_monthly_events_do_not_repeat_across_multiple_days(self):
        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("US", year=2026, month=3)

        cpi_dates = [event["date"] for event in result["events"] if event["title_en"] == "CPI Release"]
        self.assertEqual(cpi_dates, ["2026-03-10"])

    async def test_actual_economic_event_replaces_monthly_recurring_estimate(self):
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "US"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("US", year=2026, month=3)

        cpi_dates = [event["date"] for event in result["events"] if event["title_en"] == "CPI Release"]
        self.assertEqual(cpi_dates, ["2026-03-12"])


if __name__ == "__main__":
    unittest.main()
