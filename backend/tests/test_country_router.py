import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.routers import country


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_opportunities_timeout_keeps_background_build_running(self):
        completion_gate = asyncio.Event()
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
            "opportunities": [],
        }

        async def slow_builder(*args, **kwargs):
            await asyncio.sleep(0.03)
            completion_gate.set()
            return {"country_code": "KR", "opportunities": []}

        with (
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=slow_builder)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
            patch("app.routers.country.OPPORTUNITY_TIMEOUT_SECONDS", 0.001),
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertEqual(response["country_code"], "KR")
        self.assertEqual(response["detailed_scanned_count"], 0)
        self.assertEqual(response["universe_note"], "기본 종목군 quick fallback")
        await asyncio.wait_for(completion_gate.wait(), timeout=0.2)


if __name__ == "__main__":
    unittest.main()
