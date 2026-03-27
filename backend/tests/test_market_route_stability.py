import unittest
from unittest.mock import AsyncMock, patch

from app.routers.country import get_sector_performance
from app.routers.screener import screen_stocks


class MarketRouteStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_screener_skips_invalid_market_snapshots(self):
        async def snapshot_side_effect(ticker: str, period: str = "6mo"):
            if ticker == "BAD":
                return {"ticker": "BAD", "valid": False, "current_price": 0.0}
            return {
                "ticker": "GOOD",
                "valid": True,
                "name": "Valid Corp",
                "current_price": 125.0,
                "prev_close": 120.0,
                "market_cap": 2500000000,
            }

        async def stock_info_side_effect(ticker: str):
            return {
                "name": "Valid Corp",
                "sector": "Information Technology",
                "industry": "Software",
                "market_cap": 2500000000,
                "current_price": 125.0,
                "prev_close": 120.0,
                "pe_ratio": 18.5,
                "dividend_yield": 0.012,
                "52w_high": 140.0,
                "52w_low": 90.0,
            }

        get_stock_info = AsyncMock(side_effect=stock_info_side_effect)

        async def _return_fetcher(key, fetcher, ttl=None):
            return await fetcher()

        with (
            patch("app.routers.screener.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.routers.screener.get_universe",
                new=AsyncMock(return_value={"Information Technology": ["BAD", "GOOD"]}),
            ),
            patch(
                "app.routers.screener.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=snapshot_side_effect),
            ),
            patch("app.routers.screener.yfinance_client.get_stock_info", new=get_stock_info),
            patch("app.routers.screener.yfinance_client.get_price_history", new=AsyncMock(return_value=[])),
        ):
            result = await screen_stocks(
                country="KR",
                sector=None,
                market_cap_min=None,
                market_cap_max=None,
                pe_min=None,
                pe_max=None,
                dividend_yield_min=None,
                score_min=None,
                sort_by="market_cap",
                sort_dir="desc",
                limit=20,
            )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["ticker"], "GOOD")
        get_stock_info.assert_not_awaited()

    async def test_sector_performance_aggregates_live_constituent_snapshots(self):
        cache_get = AsyncMock(return_value=None)
        cache_set = AsyncMock()
        load_snapshot = AsyncMock(
            side_effect=[
                {"ticker": "AAA", "name": "Alpha", "price": 100.0, "change_pct": 2.0, "market_cap": 900.0, "current_price": 100.0, "valid": True},
                {"ticker": "BBB", "name": "Beta", "price": 80.0, "change_pct": -1.0, "market_cap": 700.0, "current_price": 80.0, "valid": True},
                {"ticker": "CCC", "name": "Care", "price": 60.0, "change_pct": 4.0, "market_cap": 500.0, "current_price": 60.0, "valid": True},
            ]
        )

        with (
            patch("app.data.cache.get", new=cache_get),
            patch("app.data.cache.set", new=cache_set),
            patch(
                "app.data.universe_data.get_universe",
                new=AsyncMock(return_value={"Information Technology": ["AAA", "BBB"], "Health Care": ["CCC"]}),
            ),
            patch("app.routers.country._load_market_snapshot", new=load_snapshot),
        ):
            result = await get_sector_performance("KR")

        self.assertEqual(result[0]["sector"], "Health Care")
        self.assertEqual(result[0]["change_pct"], 4.0)
        self.assertEqual(result[1]["sector"], "Information Technology")
        self.assertEqual(result[1]["change_pct"], 0.5)
        self.assertEqual(result[1]["ticker"], "AAA")
        cache_set.assert_awaited()


if __name__ == "__main__":
    unittest.main()
