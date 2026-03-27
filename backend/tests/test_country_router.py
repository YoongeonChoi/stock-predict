import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.routers import country


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_opportunities_timeout_keeps_background_build_running(self):
        completion_gate = asyncio.Event()

        async def slow_builder(*args, **kwargs):
            await asyncio.sleep(0.03)
            completion_gate.set()
            return {"country_code": "KR", "opportunities": []}

        with (
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=slow_builder)),
            patch("app.routers.country.OPPORTUNITY_TIMEOUT_SECONDS", 0.001),
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertEqual(response.status_code, 504)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(payload["error_code"], "SP-5018")
        self.assertIn("백그라운드 계산은 계속 진행", payload["detail"])
        await asyncio.wait_for(completion_gate.wait(), timeout=0.2)


if __name__ == "__main__":
    unittest.main()
