import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.data import fmp_client
from app.data import cache
from app.data.universe_data import EXCHANGE_MAP, get_universe, resolve_universe


class CacheAndUniverseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cache.reset_memory_cache_state()
        await cache.invalidate("unit_test:%")
        await cache.invalidate("dynamic_universe:%")
        await cache.invalidate("fmp_screen%")

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

    async def test_get_or_fetch_wait_timeout_returns_fallback_while_inflight_continues(self):
        started = asyncio.Event()

        async def slow_fetcher():
            started.set()
            await asyncio.sleep(0.05)
            return {"value": 11}

        first_task = asyncio.create_task(cache.get_or_fetch("unit_test:timeout_fallback", slow_fetcher, ttl=60))
        await started.wait()

        fallback = await cache.get_or_fetch(
            "unit_test:timeout_fallback",
            slow_fetcher,
            ttl=60,
            wait_timeout=0.001,
            timeout_fallback={"value": 5},
        )
        resolved = await first_task

        self.assertEqual(fallback, {"value": 5})
        self.assertEqual(resolved, {"value": 11})

    async def test_get_or_fetch_first_caller_can_timeout_and_background_task_still_caches(self):
        started = asyncio.Event()

        async def slow_fetcher():
            started.set()
            await asyncio.sleep(0.05)
            return {"value": 19}

        fallback = await cache.get_or_fetch(
            "unit_test:first_caller_timeout_fallback",
            slow_fetcher,
            ttl=60,
            wait_timeout=0.001,
            timeout_fallback={"value": 3},
        )
        await started.wait()
        await asyncio.sleep(0.08)
        cached = await cache.get("unit_test:first_caller_timeout_fallback")

        self.assertEqual(fallback, {"value": 3})
        self.assertEqual(cached, {"value": 19})

    async def test_memory_cache_serves_recent_value_without_database_roundtrip(self):
        await cache.set("unit_test:memory_hot", {"value": 23}, ttl=60)

        with patch("app.data.cache.db.cache_get", new=AsyncMock(side_effect=AssertionError("db cache_get should not run"))):
            cached = await cache.get("unit_test:memory_hot")

        self.assertEqual(cached, {"value": 23})

    async def test_memory_cache_enforces_entry_and_byte_limits(self):
        oversized_settings = SimpleNamespace(
            cache_ttl_price=60,
            cache_memory_max_entries=2,
            cache_memory_max_mb=1,
        )
        large_value = {"payload": "x" * 700_000}

        with (
            patch("app.data.cache.get_settings", return_value=oversized_settings),
            patch("app.data.cache.db.cache_set", new=AsyncMock()),
            patch("app.data.cache.db.cache_get", new=AsyncMock(return_value=None)),
        ):
            await cache.set("unit_test:memory_cap:1", large_value, ttl=60)
            await cache.set("unit_test:memory_cap:2", large_value, ttl=60)
            await cache.set("unit_test:memory_cap:3", large_value, ttl=60)
            stats = cache.get_memory_cache_stats()
            evicted = await cache.get("unit_test:memory_cap:1")
            newest = await cache.get("unit_test:memory_cap:3")

        self.assertLessEqual(stats["entry_count"], 2)
        self.assertLessEqual(stats["estimated_bytes"], 1 * 1024 * 1024)
        self.assertIsNone(evicted)
        self.assertIsNotNone(newest)

    async def test_memory_cache_skips_oversized_entry_but_keeps_database_persistence(self):
        constrained_settings = SimpleNamespace(
            cache_ttl_price=60,
            cache_memory_max_entries=8,
            cache_memory_max_mb=64,
            cache_memory_max_entry_mb=1,
        )
        db_cache_set = AsyncMock()
        oversized_value = {"payload": "x" * 1_500_000}

        with (
            patch("app.data.cache.get_settings", return_value=constrained_settings),
            patch("app.data.cache.db.cache_set", new=db_cache_set),
            patch("app.data.cache.db.cache_get", new=AsyncMock(return_value=None)),
        ):
            await cache.set("unit_test:memory_oversized", oversized_value, ttl=60)
            hot_value = await cache.get("unit_test:memory_oversized")
            stats = cache.get_memory_cache_stats()

        db_cache_set.assert_awaited_once()
        self.assertIsNone(hot_value)
        self.assertEqual(stats["entry_count"], 0)
        self.assertEqual(stats["skipped_oversized_writes"], 1)

    async def test_get_universe_filters_known_invalid_tickers(self):
        with patch(
            "app.data.fmp_client.probe_stock_screener",
            new=AsyncMock(return_value=False),
        ):
            universe = await get_universe("KR")
        flattened = [ticker for tickers in universe.values() for ticker in tickers]
        self.assertNotIn("091990.KS", flattened)
        self.assertNotIn("098560.KS", flattened)
        self.assertNotIn("002550.KS", flattened)
        self.assertNotIn("003410.KS", flattened)
        self.assertNotIn("010620.KS", flattened)
        self.assertIn("196170.KQ", universe["Health Care"])

    async def test_probe_stock_screener_disables_exchange_after_403(self):
        class FailingAsyncClient:
            calls = 0

            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, params=None):
                type(self).calls += 1
                request = httpx.Request("GET", url, params=params)
                response = httpx.Response(403, request=request)
                raise httpx.HTTPStatusError("Forbidden", request=request, response=response)

        with (
            patch(
                "app.data.fmp_client.get_settings",
                return_value=SimpleNamespace(fmp_api_key="demo", cache_ttl_fmp=3600),
            ),
            patch("app.data.fmp_client.httpx.AsyncClient", new=FailingAsyncClient),
        ):
            first = await fmp_client.probe_stock_screener("TSE", market_cap_min=100_000_000)
            second = await fmp_client.probe_stock_screener("TSE", market_cap_min=100_000_000)

        self.assertFalse(first)
        self.assertFalse(second)
        self.assertEqual(FailingAsyncClient.calls, 1)
        status = await fmp_client.get_screening_status("TSE")
        self.assertEqual(status["status_code"], 403)

    async def test_resolve_universe_returns_fallback_metadata_when_probe_fails(self):
        probe_mock = AsyncMock(return_value=False)
        with (
            patch(
                "app.data.universe_data.get_settings",
                return_value=SimpleNamespace(fmp_api_key="demo"),
            ),
            patch(
                "app.data.fmp_client.probe_stock_screener",
                new=probe_mock,
            ),
        ):
            selection = await resolve_universe("KR")

        self.assertEqual(selection.source, "fallback")
        self.assertTrue(selection.note)
        self.assertEqual(selection.sectors["Information Technology"][0], "005930.KS")
        self.assertEqual(probe_mock.await_count, len(EXCHANGE_MAP["KR"]))


if __name__ == "__main__":
    unittest.main()
