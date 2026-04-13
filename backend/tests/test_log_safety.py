import unittest
import warnings
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd

from app.analysis.distributional import price_encoder
from app.analysis.historical_pattern_forecast import build_historical_pattern_forecast
from app.analysis.market_regime import build_market_regime
from app.data import yfinance_client
from app.scoring.fear_greed import _volatility_score


def _series(days: int = 420, drift: float = 0.002, volatility: float = 0.018, start: float = 100.0):
    rows = []
    price = start
    base = date(2024, 1, 1)
    for idx in range(days):
        cycle = ((idx % 30) - 15) / 1000
        shock = ((idx % 11) - 5) / 1000 * volatility
        change = drift + cycle + shock
        next_price = max(price * (1 + change), 5)
        high = max(price, next_price) * 1.01
        low = min(price, next_price) * 0.99
        rows.append(
            {
                "date": (base + timedelta(days=idx)).isoformat(),
                "open": round(price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(next_price, 2),
                "volume": 1_000_000 + (idx % 20) * 18_000,
            }
        )
        price = next_price
    return rows


def _runtime_warnings(captured):
    return [warning for warning in captured if issubclass(warning.category, RuntimeWarning)]


class LogSafetyTests(unittest.TestCase):
    def test_price_encoder_return_series_ignores_non_positive_prices_without_warning(self):
        close = pd.Series([100.0, 0.0, -5.0, 102.0, 104.0], dtype=float)

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            returns = price_encoder.return_series(close)

        self.assertTrue(np.all(np.isfinite(returns)))
        self.assertEqual(len(returns), 1)
        self.assertFalse(_runtime_warnings(captured), captured)

    def test_market_regime_ignores_non_positive_prices_without_warning(self):
        history = _series(days=90)
        history[20]["close"] = 0.0
        history[21]["close"] = -3.0

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            regime = build_market_regime(
                country_code="KR",
                name="KOSPI",
                price_history=history,
                breadth_ratio=0.7,
            )

        self.assertTrue(np.isfinite(regime.score))
        self.assertFalse(_runtime_warnings(captured), captured)

    def test_historical_pattern_forecast_skips_non_positive_subpaths_without_warning(self):
        stock_history = _series()
        market_history = _series(start=200.0, drift=0.0015, volatility=0.012)
        stock_history[180]["close"] = 0.0
        stock_history[181]["close"] = -4.0

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            forecast, backtest = build_historical_pattern_forecast(
                ticker="TEST",
                name="Test Corp",
                country_code="KR",
                price_history=stock_history,
                market_history=market_history,
            )

        self.assertIsNotNone(forecast)
        self.assertIsNotNone(backtest)
        self.assertFalse(_runtime_warnings(captured), captured)

    def test_fear_greed_volatility_score_ignores_non_positive_closes_without_warning(self):
        prices = _series(days=30)
        prices[10]["close"] = 0.0
        prices[11]["close"] = -1.0

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            score = _volatility_score(None, prices)

        self.assertTrue(np.isfinite(score))
        self.assertFalse(_runtime_warnings(captured), captured)


class YFinanceLogSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_historical_returns_ignores_non_positive_closes_without_warning(self):
        frame = pd.DataFrame(
            {
                "Close": [100.0, 0.0, -2.0, 103.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0, 118.0]
            }
        )

        async def _return_fetcher(_key, fetcher, ttl=None, **kwargs):
            return await fetcher()

        with (
            warnings.catch_warnings(record=True) as captured,
            patch("app.data.yfinance_client._history_sync", return_value=frame),
            patch("app.data.yfinance_client.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
        ):
            warnings.simplefilter("always")
            returns = await yfinance_client.get_historical_returns("005930.KS", days=5)

        self.assertTrue(all(np.isfinite(value) for value in returns))
        self.assertGreater(len(returns), 0)
        self.assertFalse(_runtime_warnings(captured), captured)
