import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import calendar_service


class CalendarServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_calendar_returns_month_scoped_events(self):
        earning_rows = [
            {"date": "2026-03-19", "symbol": "005930.KS", "time": "bmo", "epsEstimated": 2.1},
        ]
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "KR"},
            {"date": "2026-03-25", "event": "Exports / Imports", "country": "Korea"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=earning_rows)),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        self.assertEqual(result["country_code"], "KR")
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
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        cpi_dates = [
            event["date"]
            for event in result["events"]
            if event["title_en"] == "CPI Release" and event["country_code"] == "KR"
        ]
        self.assertEqual(len(cpi_dates), 1)
        self.assertIn("한국과 해외 핵심 일정", result["summary"]["note"])

    async def test_actual_economic_event_replaces_monthly_recurring_estimate(self):
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "KR"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        cpi_dates = [
            event["date"]
            for event in result["events"]
            if event["title_en"] == "CPI Release" and event["country_code"] == "KR"
        ]
        self.assertEqual(cpi_dates, ["2026-03-12"])

    async def test_calendar_includes_tracked_global_macro_and_earnings_events(self):
        earning_rows = [
            {"date": "2026-03-20", "symbol": "NVDA", "time": "amc", "epsEstimated": 5.1},
        ]
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "US"},
            {"date": "2026-03-19", "event": "Interest Rate Decision", "country": "Euro Area"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=earning_rows)),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        self.assertTrue(
            any(
                event["country_code"] == "US" and event["title"] == "미국 CPI 발표"
                for event in result["economic_events"]
            )
        )
        self.assertTrue(
            any(
                event["country_code"] == "EU" and event["title"] == "ECB 금리결정"
                for event in result["economic_events"]
            )
        )
        self.assertTrue(
            any(
                event["country_code"] == "US" and event.get("symbol") == "NVDA"
                for event in result["earnings_events"]
            )
        )

    async def test_global_actual_event_does_not_remove_korea_recurring_event(self):
        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "US"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        self.assertTrue(
            any(
                event["country_code"] == "KR" and event["title_en"] == "CPI Release"
                for event in result["events"]
            )
        )
        self.assertTrue(
            any(
                event["country_code"] == "US" and event["title_en"] == "CPI Release"
                for event in result["events"]
            )
        )

    async def test_calendar_returns_partial_with_available_source_data_when_one_feed_is_slow(self):
        async def _slow_earnings():
            await asyncio.sleep(0.05)
            return [{"date": "2026-03-19", "symbol": "005930.KS", "time": "bmo", "epsEstimated": 2.1}]

        economic_rows = [
            {"date": "2026-03-12", "event": "CPI Release", "country": "KR"},
        ]

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.CALENDAR_SOURCE_WAIT_TIMEOUT_SECONDS", 0.01),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(side_effect=_slow_earnings)),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=economic_rows)),
            patch("app.services.calendar_service.fmp_client.get_feature_status", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=3)

        self.assertTrue(result["partial"])
        self.assertEqual(result["fallback_reason"], "calendar_live_partial_data")
        self.assertTrue(any(event["title_en"] == "CPI Release" for event in result["events"]))
        self.assertGreater(result["summary"]["total_events"], 0)

    async def test_calendar_marks_external_source_unavailable_when_fmp_feature_is_disabled(self):
        disabled_status = {"status_code": 403, "detail": "quota"}

        with (
            patch("app.services.calendar_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.calendar_service.cache.set", new=AsyncMock()),
            patch("app.services.calendar_service.fmp_client.get_earning_calendar", new=AsyncMock(return_value=[])),
            patch("app.services.calendar_service.fmp_client.get_economic_calendar", new=AsyncMock(return_value=[])),
            patch(
                "app.services.calendar_service.fmp_client.get_feature_status",
                new=AsyncMock(side_effect=[disabled_status, disabled_status]),
            ),
            patch("app.services.calendar_service.get_settings", return_value=SimpleNamespace(cache_ttl_news=60)),
        ):
            result = await calendar_service.get_calendar("KR", year=2026, month=4)

        self.assertTrue(result["partial"])
        self.assertEqual(result["fallback_reason"], "calendar_external_source_unavailable")
        self.assertIn("외부 캘린더 공급 제한", result["summary"]["note"])


if __name__ == "__main__":
    unittest.main()
