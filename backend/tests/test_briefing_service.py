import asyncio
import unittest
import time
from unittest.mock import AsyncMock, patch

from app.services import briefing_service


class BriefingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_daily_briefing_persists_last_success_snapshot(self):
        radar_payload = {
            "country_code": "KR",
            "generated_at": "2026-04-12T09:00:00",
            "market_regime": {
                "label": "상승 우위",
                "stance": "risk_on",
                "conviction": 71.2,
                "summary": "상위 후보가 유지되고 있습니다.",
            },
            "total_scanned": 200,
            "actionable_count": 6,
            "bullish_count": 18,
            "universe_source": "cache",
            "universe_note": "cached",
            "opportunities": [
                {
                    "ticker": "005930.KS",
                    "name": "삼성전자",
                    "sector": "Information Technology",
                    "action": "분할 매수",
                    "up_probability": 68.4,
                    "confidence": 54.2,
                    "predicted_return_pct": 2.3,
                    "execution_note": "대표 후보 유지",
                }
            ],
        }
        cache_set = AsyncMock(return_value=None)
        with (
            patch("app.services.briefing_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.briefing_service.cache.set", new=cache_set),
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
            patch(
                "app.services.briefing_service.db.research_report_status",
                new=AsyncMock(return_value={"todays_reports": 0, "total_reports": 0, "source_count": 0, "last_synced_at": None}),
            ),
            patch("app.services.briefing_service._upcoming_events", new=AsyncMock(return_value=[])),
            patch(
                "app.services.briefing_service.market_service.get_cached_market_opportunities",
                new=AsyncMock(return_value=radar_payload),
            ),
        ):
            result = await briefing_service.get_daily_briefing()

        self.assertFalse(result["partial"])
        self.assertEqual(cache_set.await_count, 2)
        written_keys = [call.args[0] for call in cache_set.await_args_list]
        self.assertTrue(any(str(key).startswith("daily_briefing:v1:") for key in written_keys))
        self.assertTrue(any(str(key).startswith("daily_briefing:last_success:v1:") for key in written_keys))

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
