import unittest
from datetime import date, timedelta

from app.analysis.historical_pattern_forecast import build_historical_pattern_forecast


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


class HistoricalPatternForecastTests(unittest.TestCase):
    def test_builds_multi_horizon_forecast_and_backtest(self):
        stock_history = _series()
        market_history = _series(start=200.0, drift=0.0015, volatility=0.012)

        forecast, backtest = build_historical_pattern_forecast(
            ticker="TEST",
            name="Test Corp",
            country_code="US",
            price_history=stock_history,
            market_history=market_history,
        )

        self.assertIsNotNone(forecast)
        self.assertIsNotNone(backtest)
        assert forecast is not None
        assert backtest is not None
        self.assertEqual([item.horizon_days for item in forecast.horizons], [5, 20, 60])
        self.assertGreaterEqual(forecast.analog_count, 12)
        self.assertEqual(len(forecast.projected_path), 60)
        self.assertGreaterEqual(backtest.win_rate, 0)
        self.assertLessEqual(backtest.win_rate, 100)

    def test_returns_none_when_history_is_too_short(self):
        forecast, backtest = build_historical_pattern_forecast(
            ticker="SHORT",
            name="Short History",
            country_code="US",
            price_history=_series(days=120),
            market_history=None,
        )
        self.assertIsNone(forecast)
        self.assertIsNone(backtest)


if __name__ == "__main__":
    unittest.main()
