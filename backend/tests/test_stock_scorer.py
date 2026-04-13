import warnings
import unittest

from app.scoring.stock_scorer import _calc_max_drawdown, _calc_return, _calc_volatility


class StockScorerTests(unittest.TestCase):
    def test_calc_volatility_ignores_invalid_close_values_without_runtime_warning(self):
        prices = [
            {"close": 100.0},
            {"close": 101.0},
            {"close": 102.5},
            {"close": 0.0},
            {"close": 103.2},
            {"close": 104.0},
            {"close": float("nan")},
            {"close": 105.6},
            {"close": 106.4},
            {"close": 107.1},
            {"close": 108.0},
            {"close": 109.3},
        ]

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            volatility = _calc_volatility(prices)

        self.assertIsNotNone(volatility)
        self.assertEqual(captured, [])

    def test_return_and_drawdown_skip_non_positive_or_invalid_closes(self):
        prices = [
            {"close": 0.0},
            {"close": 100.0},
            {"close": 110.0},
            {"close": float("nan")},
            {"close": 90.0},
        ]

        self.assertEqual(_calc_return(prices), -10.0)
        self.assertEqual(_calc_max_drawdown(prices), 18.2)


if __name__ == "__main__":
    unittest.main()
