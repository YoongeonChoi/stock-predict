import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services import briefing_service


async def _slow_radar(*args, **kwargs):
    await asyncio.sleep(0.05)
    return {}


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
            patch("app.services.briefing_service.BRIEFING_RADAR_TIMEOUT_SECONDS", 0.01),
            patch("app.services.briefing_service.market_service.get_market_opportunities", new=AsyncMock(side_effect=_slow_radar)),
        ):
            result = await briefing_service.get_daily_briefing()

        self.assertEqual(result["market_view"][0]["country_code"], "KR")
        self.assertEqual(result["focus_cards"], [])
        self.assertIn("요약만 표시합니다", result["market_view"][0]["summary"])


if __name__ == "__main__":
    unittest.main()
