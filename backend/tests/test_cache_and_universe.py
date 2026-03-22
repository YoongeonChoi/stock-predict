import asyncio
import unittest

from app.data import cache
from app.data.universe_data import get_universe


class CacheAndUniverseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await cache.invalidate("unit_test:%")

    async def test_get_or_fetch_deduplicates_inflight_requests(self):
        calls = 0

        async def fetcher():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return {"value": 7}

        results = await asyncio.gather(
            cache.get_or_fetch("unit_test:inflight", fetcher, ttl=60),
            cache.get_or_fetch("unit_test:inflight", fetcher, ttl=60),
            cache.get_or_fetch("unit_test:inflight", fetcher, ttl=60),
        )

        self.assertEqual(calls, 1)
        self.assertEqual(results[0], {"value": 7})
        self.assertEqual(results[1], {"value": 7})
        self.assertEqual(results[2], {"value": 7})

    async def test_get_universe_filters_known_invalid_tickers(self):
        universe = await get_universe("KR")
        flattened = [ticker for tickers in universe.values() for ticker in tickers]
        self.assertNotIn("091990.KS", flattened)
        self.assertIn("196170.KQ", universe["Health Care"])


if __name__ == "__main__":
    unittest.main()
