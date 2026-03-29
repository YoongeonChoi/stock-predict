import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from app.routers import country
from app.runtime import reset_runtime_state


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_runtime_state()

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

    async def test_spawn_opportunity_refresh_reuses_existing_background_job(self):
        first_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def slow_builder(*args, **kwargs):
            first_started.set()
            await release_refresh.wait()
            return {"country_code": "KR", "opportunities": []}

        refresh_builder = AsyncMock(side_effect=slow_builder)

        with patch("app.routers.country.market_service.get_market_opportunities", new=refresh_builder):
            country._spawn_opportunity_refresh("KR", 17)
            await asyncio.wait_for(first_started.wait(), timeout=0.2)
            country._spawn_opportunity_refresh("KR", 17)
            await asyncio.sleep(0.01)
            self.assertEqual(refresh_builder.await_count, 1)
            release_refresh.set()
            await asyncio.sleep(0.01)

    async def test_list_countries_returns_fallback_when_payload_times_out(self):
        async def _slow_payload():
            await asyncio.sleep(0.03)
            return []

        async def _return_fetcher(_key, fetcher, ttl=None):
            return await fetcher()

        with (
            patch("app.routers.country.COUNTRIES_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country._build_countries_payload", new=AsyncMock(side_effect=_slow_payload)),
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
        ):
            response = await country.list_countries()

        self.assertTrue(response)
        self.assertEqual(response[0]["indices"][0]["price"], 0)
        self.assertEqual(response[0]["indices"][0]["change_pct"], 0)

    async def test_market_movers_prefers_kr_representative_quotes(self):
        representative_quotes = {
            "005930.KS": {
                "ticker": "005930.KS",
                "name": "Samsung Electronics",
                "current_price": 71200.0,
                "change_pct": 2.4,
            },
            "000660.KS": {
                "ticker": "000660.KS",
                "name": "SK hynix",
                "current_price": 182000.0,
                "change_pct": -1.2,
            },
        }

        async def _return_fetcher(_key, fetcher, ttl=None):
            return await fetcher()

        with (
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.routers.country.kr_market_quote_client.get_kr_representative_quotes",
                new=AsyncMock(return_value=representative_quotes),
            ) as representative_loader,
            patch(
                "app.data.universe_data.get_universe",
                new=AsyncMock(side_effect=AssertionError("KR representative quotes should avoid the universe fallback")),
            ),
        ):
            response = await country.get_market_movers("KR")

        self.assertEqual(response["gainers"][0]["ticker"], "005930.KS")
        self.assertEqual(response["losers"][0]["ticker"], "000660.KS")
        representative_loader.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
