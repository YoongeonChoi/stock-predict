import unittest
from unittest.mock import AsyncMock, patch

from app.routers.screener import screen_stocks


class ScreenerFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_screener_supports_extended_quality_filters(self):
        universe = {"Information Technology": ["005930.KS", "000660.KS"]}
        market_snapshots = {
            "005930.KS": {"valid": True, "current_price": 70000.0, "market_cap": 420000000000.0, "prev_close": 69000.0, "name": "Samsung Electronics"},
            "000660.KS": {"valid": True, "current_price": 180000.0, "market_cap": 130000000000.0, "prev_close": 178000.0, "name": "SK hynix"},
        }
        stock_info = {
            "005930.KS": {
                "name": "Samsung Electronics",
                "sector": "Information Technology",
                "industry": "Semiconductors",
                "market_cap": 420000000000.0,
                "current_price": 70000.0,
                "prev_close": 69000.0,
                "pe_ratio": 14.0,
                "pb_ratio": 1.2,
                "dividend_yield": 0.024,
                "beta": 0.92,
                "52w_high": 80000.0,
                "52w_low": 61000.0,
                "revenue_growth": 0.11,
                "roe": 0.15,
                "debt_to_equity": 24.0,
                "avg_volume": 18000000.0,
                "profit_margins": 0.18,
            },
            "000660.KS": {
                "name": "SK hynix",
                "sector": "Information Technology",
                "industry": "Semiconductors",
                "market_cap": 130000000000.0,
                "current_price": 180000.0,
                "prev_close": 178000.0,
                "pe_ratio": 48.0,
                "pb_ratio": 3.4,
                "dividend_yield": 0.005,
                "beta": 1.55,
                "52w_high": 205000.0,
                "52w_low": 118000.0,
                "revenue_growth": 0.04,
                "roe": 0.07,
                "debt_to_equity": 68.0,
                "avg_volume": 4200000.0,
                "profit_margins": 0.06,
            },
        }

        async def market_snapshot_side_effect(ticker: str, period: str = "6mo"):
            return market_snapshots[ticker]

        async def stock_info_side_effect(ticker: str):
            return stock_info[ticker]

        with (
            patch("app.routers.screener.cache.get", new=AsyncMock(return_value=None)),
            patch("app.routers.screener.cache.set", new=AsyncMock()),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value=universe)),
            patch("app.routers.screener.yfinance_client.get_market_snapshot", new=AsyncMock(side_effect=market_snapshot_side_effect)),
            patch("app.routers.screener.yfinance_client.get_stock_info", new=AsyncMock(side_effect=stock_info_side_effect)),
        ):
            result = await screen_stocks(
                country="KR",
                sector="Information Technology",
                pe_max=20,
                pb_max=2,
                beta_max=1.1,
                revenue_growth_min=8,
                roe_min=10,
                debt_to_equity_max=30,
                avg_volume_min=10000000,
                profitable_only=True,
                sort_by="roe",
                sort_dir="desc",
                limit=20,
            )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["ticker"], "005930.KS")
        self.assertEqual(result["results"][0]["roe"], 15.0)
        self.assertEqual(result["results"][0]["revenue_growth"], 11.0)


if __name__ == "__main__":
    unittest.main()
