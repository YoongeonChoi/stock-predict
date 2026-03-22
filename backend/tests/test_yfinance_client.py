import unittest
from unittest.mock import patch

import pandas as pd

from app.data import yfinance_client


class _FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.info = {}
        self.fast_info = {"lastPrice": 101.5, "previousClose": 100.0, "marketCap": 123456789}
        self.history_metadata = {
            "shortName": "Fallback Corp",
            "fiftyTwoWeekHigh": 123.4,
            "fiftyTwoWeekLow": 87.6,
            "regularMarketPrice": 101.5,
            "previousClose": 100.0,
        }
        self.calendar = {
            "Earnings Date": [pd.Timestamp("2026-04-28")],
            "EPS Estimate": 1.23,
            "Reported EPS": 1.31,
            "Surprise(%)": 6.5,
        }

    @property
    def earnings_dates(self):
        raise ImportError("Missing optional dependency 'lxml'")

    @property
    def quarterly_income_stmt(self):
        return pd.DataFrame()

    @property
    def quarterly_cashflow(self):
        return pd.DataFrame()

    @property
    def recommendations(self):
        return pd.DataFrame()


async def _passthrough_cache(_key, fetch, _ttl):
    return await fetch()


class YFinanceClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_stock_info_uses_history_and_metadata_fallbacks(self):
        history = pd.DataFrame(
            {
                "Open": [98.0, 100.0],
                "High": [102.0, 104.0],
                "Low": [97.0, 99.0],
                "Close": [100.0, 101.5],
                "Volume": [1_200_000, 1_400_000],
            },
            index=pd.to_datetime(["2026-03-20", "2026-03-23"]),
        )

        with (
            patch("app.data.yfinance_client.cache.get_or_fetch", new=_passthrough_cache),
            patch("app.data.yfinance_client.yf.Ticker", side_effect=lambda ticker: _FakeTicker(ticker)),
            patch("app.data.yfinance_client._history_sync", return_value=history),
            patch("app.data.yfinance_client._history_based_quote", return_value={"ticker": "TEST", "price": 101.5, "prev_close": 100.0, "change_pct": 1.5}),
        ):
            info = await yfinance_client.get_stock_info("TEST")

        self.assertEqual(info["name"], "Fallback Corp")
        self.assertEqual(info["current_price"], 101.5)
        self.assertEqual(info["prev_close"], 100.0)
        self.assertEqual(info["52w_high"], 123.4)
        self.assertEqual(info["52w_low"], 87.6)

    async def test_get_earnings_history_falls_back_to_calendar_without_lxml(self):
        with (
            patch("app.data.yfinance_client.cache.get_or_fetch", new=_passthrough_cache),
            patch("app.data.yfinance_client.yf.Ticker", side_effect=lambda ticker: _FakeTicker(ticker)),
        ):
            rows = await yfinance_client.get_earnings_history("TEST")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-04-28")
        self.assertEqual(rows[0]["eps_estimate"], 1.23)
        self.assertEqual(rows[0]["eps_actual"], 1.31)


if __name__ == "__main__":
    unittest.main()
