import unittest
from unittest.mock import AsyncMock, patch

import pandas as pd

from app.data import yfinance_client


class _FakeTicker:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.info = {
            "currentPrice": 99.0,
            "regularMarketPrice": 99.0,
            "previousClose": 98.5,
        }
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


async def _passthrough_cache(_key, fetch, _ttl, **kwargs):
    return await fetch()


class YFinanceClientTests(unittest.IsolatedAsyncioTestCase):
    def test_batch_quote_chunk_size_avoids_slow_80_name_slice(self):
        self.assertEqual(yfinance_client._batch_quote_chunk_size(201), 240)
        self.assertEqual(yfinance_client._batch_quote_chunk_size(100), 120)
        self.assertEqual(yfinance_client._batch_quote_chunk_size(12), 12)

    async def test_get_batch_stock_quotes_parses_multi_ticker_download(self):
        columns = pd.MultiIndex.from_tuples(
            [
                ("005930.KS", "Open"),
                ("005930.KS", "High"),
                ("005930.KS", "Low"),
                ("005930.KS", "Close"),
                ("005930.KS", "Volume"),
                ("000660.KS", "Open"),
                ("000660.KS", "High"),
                ("000660.KS", "Low"),
                ("000660.KS", "Close"),
                ("000660.KS", "Volume"),
            ],
            names=["Ticker", "Price"],
        )
        download_df = pd.DataFrame(
            [
                [70000.0, 71000.0, 69500.0, 70500.0, 1000000, 120000.0, 123000.0, 119000.0, 121000.0, 800000],
                [70800.0, 71500.0, 70200.0, 71200.0, 1100000, 121500.0, 124000.0, 120500.0, 123500.0, 850000],
            ],
            index=pd.to_datetime(["2026-03-26", "2026-03-27"]),
            columns=columns,
        )

        cache_set = AsyncMock()

        with (
            patch("app.data.yfinance_client.cache.get_or_fetch", new=_passthrough_cache),
            patch("app.data.yfinance_client.cache.set", new=cache_set),
            patch("app.data.yfinance_client.yf.download", return_value=download_df),
            patch("app.data.yfinance_client.latest_closed_trading_day", return_value=pd.Timestamp("2026-03-27").date()),
        ):
            quotes = await yfinance_client.get_batch_stock_quotes(["005930.KS", "000660.KS"])

        self.assertEqual(set(quotes.keys()), {"005930.KS", "000660.KS"})
        self.assertEqual(quotes["005930.KS"]["current_price"], 71200.0)
        self.assertEqual(quotes["005930.KS"]["prev_close"], 70500.0)
        self.assertAlmostEqual(quotes["000660.KS"]["change_pct"], round(((123500.0 - 121000.0) / 121000.0) * 100.0, 2))
        self.assertEqual(cache_set.await_count, 2)

    async def test_get_batch_stock_quotes_skips_individual_cache_priming_for_large_batch(self):
        tickers = [f"{index:06d}.KS" for index in range(yfinance_client.BATCH_QUOTE_PRIME_LIMIT + 2)]
        columns = []
        row_one = []
        row_two = []
        for index, ticker in enumerate(tickers):
            base = 100.0 + index
            columns.extend(
                [
                    (ticker, "Open"),
                    (ticker, "High"),
                    (ticker, "Low"),
                    (ticker, "Close"),
                    (ticker, "Volume"),
                ]
            )
            row_one.extend([base - 1.0, base + 1.0, base - 2.0, base, 100000 + index])
            row_two.extend([base, base + 2.0, base - 1.0, base + 0.5, 120000 + index])

        download_df = pd.DataFrame(
            [row_one, row_two],
            index=pd.to_datetime(["2026-03-26", "2026-03-27"]),
            columns=pd.MultiIndex.from_tuples(columns, names=["Ticker", "Price"]),
        )
        cache_set = AsyncMock()

        with (
            patch("app.data.yfinance_client.cache.get_or_fetch", new=_passthrough_cache),
            patch("app.data.yfinance_client.cache.set", new=cache_set),
            patch("app.data.yfinance_client.yf.download", return_value=download_df),
            patch("app.data.yfinance_client.latest_closed_trading_day", return_value=pd.Timestamp("2026-03-27").date()),
        ):
            quotes = await yfinance_client.get_batch_stock_quotes(tickers)

        self.assertEqual(len(quotes), len(tickers))
        self.assertEqual(cache_set.await_count, 0)

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
        ):
            info = await yfinance_client.get_stock_info("TEST")

        self.assertEqual(info["name"], "Fallback Corp")
        self.assertEqual(info["current_price"], 101.5)
        self.assertEqual(info["prev_close"], 100.0)
        self.assertEqual(info["52w_high"], 123.4)
        self.assertEqual(info["52w_low"], 87.6)

    async def test_get_index_quote_uses_versioned_cache_key_and_skips_zero_payload_caching(self):
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
        cache_get_or_fetch = AsyncMock(side_effect=_passthrough_cache)

        with (
            patch("app.data.yfinance_client.cache.get_or_fetch", new=cache_get_or_fetch),
            patch("app.data.yfinance_client.yf.Ticker", side_effect=lambda ticker: _FakeTicker(ticker)),
            patch("app.data.yfinance_client._history_sync", return_value=history),
        ):
            quote = await yfinance_client.get_index_quote("USDKRW=X")

        key, _, _ = cache_get_or_fetch.await_args.args
        should_cache = cache_get_or_fetch.await_args.kwargs["should_cache"]

        self.assertTrue(key.startswith("index:v2:USDKRW=X:"))
        self.assertGreater(quote["price"], 0.0)
        self.assertFalse(should_cache({"price": 0.0, "prev_close": 0.0, "change_pct": 0.0}))
        self.assertTrue(should_cache({"price": 1380.2, "prev_close": 1375.1, "change_pct": 0.37}))

    def test_completed_history_df_drops_unfinished_daily_bar(self):
        history = pd.DataFrame(
            {
                "Open": [98.0, 100.0, 105.0],
                "High": [102.0, 104.0, 106.0],
                "Low": [97.0, 99.0, 103.0],
                "Close": [100.0, 101.5, 104.5],
                "Volume": [1_200_000, 1_400_000, 900_000],
            },
            index=pd.to_datetime(["2026-03-20", "2026-03-23", "2026-03-24"]),
        )

        with patch("app.data.yfinance_client.latest_closed_trading_day", return_value=pd.Timestamp("2026-03-23").date()):
            filtered = yfinance_client._completed_history_df(history, "AAPL")

        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered.index[-1].strftime("%Y-%m-%d"), "2026-03-23")

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
