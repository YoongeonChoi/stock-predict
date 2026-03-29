import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.routers import country


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_opportunities_returns_quick_and_starts_background_refresh(self):
        refresh_started = asyncio.Event()
        quick_payload = {
            "country_code": "KR",
            "generated_at": "2026-03-27T12:00:00",
            "market_regime": None,
            "universe_size": 201,
            "total_scanned": 201,
            "quote_available_count": 180,
            "detailed_scanned_count": 0,
            "actionable_count": 6,
            "bullish_count": 4,
            "universe_source": "fallback",
            "universe_note": "기본 종목군 quick fallback",
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }

        async def slow_builder(*args, **kwargs):
            refresh_started.set()
            await asyncio.sleep(0.03)
            return {"country_code": "KR", "opportunities": []}

        with (
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=slow_builder)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertEqual(response["country_code"], "KR")
        self.assertEqual(response["detailed_scanned_count"], 0)
        self.assertIn("quick fallback", response["universe_note"])
        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "opportunity_quick_response")
        await asyncio.wait_for(refresh_started.wait(), timeout=0.2)


if __name__ == "__main__":
    unittest.main()
