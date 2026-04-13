import asyncio
import unittest
import time
from unittest.mock import AsyncMock, patch

from app.services import briefing_service


class BriefingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_briefing_falls_back_when_radar_is_slow(self):
        with (
            patch("app.services.briefing_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.briefing_service.cache.set", new=AsyncMock(return_value=None)),
            patch(
                "app.services.briefing_service.market_session_service.get_market_sessions",
                new=AsyncMock(
                    return_value={
                        "sessions": [
                            {
                                "country_code": "KR",
                                "name_local": "한국",
                                "is_open": False,
                            }
                        ]
                    }
                ),
            ),
            patch("app.services.briefing_service.db.research_report_status", new=AsyncMock(return_value={"todays_reports": 0, "total_reports": 0, "source_count": 0, "last_synced_at": None})),
            patch("app.services.briefing_service._upcoming_events", new=AsyncMock(return_value=[])),
            patch("app.services.briefing_service._briefing_radar_request_timeout_seconds", return_value=0.01),
            patch("app.services.briefing_service.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.services.briefing_service.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch(
                "app.services.briefing_service.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=TimeoutError),
            ),
        ):
            result = await briefing_service.get_daily_briefing()

        self.assertEqual(result["market_view"][0]["country_code"], "KR")
        self.assertTrue(result["partial"])
        self.assertEqual(result["fallback_reason"], "briefing_partial_snapshot")
        self.assertEqual(result["focus_cards"], [])
        self.assertIn("요약만 표시합니다", result["market_view"][0]["summary"])

    async def test_daily_briefing_returns_partial_without_waiting_for_late_radar_cleanup(self):
        async def _slow_radar(*args, **kwargs):
            try:
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                await asyncio.sleep(0.05)
                return {
                    "country_code": "KR",
                    "generated_at": "2026-04-10T09:00:00",
                    "market_regime": {"label": "지연", "stance": "neutral", "conviction": 0, "summary": "late"},
                    "total_scanned": 0,
                    "actionable_count": 0,
                    "bullish_count": 0,
                    "universe_source": "late",
                    "universe_note": "late",
                    "opportunities": [],
                }
            return {
                "country_code": "KR",
                "generated_at": "2026-04-10T09:00:00",
                "market_regime": {"label": "지연", "stance": "neutral", "conviction": 0, "summary": "late"},
                "total_scanned": 0,
                "actionable_count": 0,
                "bullish_count": 0,
                "universe_source": "late",
                "universe_note": "late",
                "opportunities": [],
            }

        with (
            patch("app.services.briefing_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.briefing_service.cache.set", new=AsyncMock(return_value=None)),
            patch(
                "app.services.briefing_service.market_session_service.get_market_sessions",
                new=AsyncMock(
                    return_value={
                        "sessions": [
                            {
                                "country_code": "KR",
                                "name_local": "한국",
                                "is_open": False,
                            }
                        ]
                    }
                ),
            ),
            patch("app.services.briefing_service.db.research_report_status", new=AsyncMock(return_value={"todays_reports": 0, "total_reports": 0, "source_count": 0, "last_synced_at": None})),
            patch("app.services.briefing_service._upcoming_events", new=AsyncMock(return_value=[])),
            patch("app.services.briefing_service._briefing_radar_request_timeout_seconds", return_value=0.01),
            patch("app.services.briefing_service.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.services.briefing_service.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch(
                "app.services.briefing_service.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=_slow_radar),
            ),
        ):
            started_at = time.perf_counter()
            result = await briefing_service.get_daily_briefing()
            elapsed = time.perf_counter() - started_at
            await asyncio.sleep(0.07)

        self.assertLess(elapsed, 0.04)
        self.assertTrue(result["partial"])
        self.assertEqual(result["fallback_reason"], "briefing_partial_snapshot")
        self.assertEqual(result["focus_cards"], [])
        self.assertIn("요약만 표시합니다", result["market_view"][0]["summary"])


if __name__ == "__main__":
    unittest.main()
