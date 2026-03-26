import unittest

from app.services.portfolio_optimizer import optimize_portfolio_weights


def _candidate(
    *,
    key: str,
    country_code: str,
    sector: str,
    current_weight_pct: float,
    model_score: float,
    expected_return_pct_20d: float,
    expected_excess_return_pct_20d: float,
    up_probability_20d: float,
    down_probability_20d: float,
    volatility_pct_20d: float,
    returns: list[float],
) -> dict:
    return {
        "key": key,
        "ticker": key,
        "country_code": country_code,
        "sector": sector,
        "current_weight_pct": current_weight_pct,
        "model_score": model_score,
        "expected_return_pct_20d": expected_return_pct_20d,
        "expected_excess_return_pct_20d": expected_excess_return_pct_20d,
        "up_probability_20d": up_probability_20d,
        "down_probability_20d": down_probability_20d,
        "forecast_volatility_pct_20d": volatility_pct_20d,
        "return_series": [
            (f"2026-03-{index + 1:02d}", value)
            for index, value in enumerate(returns)
        ],
    }


class PortfolioOptimizerTests(unittest.TestCase):
    def test_optimize_portfolio_weights_respects_caps_and_outputs_20d_summary(self):
        candidates = [
            _candidate(
                key="005930.KS",
                country_code="KR",
                sector="Information Technology",
                current_weight_pct=18.0,
                model_score=83.0,
                expected_return_pct_20d=4.2,
                expected_excess_return_pct_20d=2.8,
                up_probability_20d=64.0,
                down_probability_20d=18.0,
                volatility_pct_20d=7.8,
                returns=[0.012, -0.004, 0.009, 0.011, -0.002, 0.008, 0.007, 0.006],
            ),
            _candidate(
                key="035420.KS",
                country_code="KR",
                sector="Communication Services",
                current_weight_pct=10.0,
                model_score=78.0,
                expected_return_pct_20d=3.4,
                expected_excess_return_pct_20d=2.1,
                up_probability_20d=60.0,
                down_probability_20d=20.0,
                volatility_pct_20d=6.9,
                returns=[0.008, 0.002, -0.003, 0.007, 0.005, -0.001, 0.006, 0.004],
            ),
            _candidate(
                key="AAPL",
                country_code="US",
                sector="Information Technology",
                current_weight_pct=6.0,
                model_score=74.0,
                expected_return_pct_20d=2.9,
                expected_excess_return_pct_20d=1.7,
                up_probability_20d=58.0,
                down_probability_20d=22.0,
                volatility_pct_20d=8.4,
                returns=[0.006, -0.005, 0.004, 0.005, -0.002, 0.003, 0.004, 0.005],
            ),
        ]
        budget = {
            "style": "balanced",
            "recommended_equity_pct": 78.0,
            "max_single_weight_pct": 34.0,
            "max_country_weight_pct": 55.0,
            "max_sector_weight_pct": 50.0,
        }

        result = optimize_portfolio_weights(candidates, budget)

        weights = result.target_weights
        self.assertLessEqual(sum(weights.values()), 78.0 + 0.2)
        self.assertGreater(result.actual_equity_pct, 0.0)
        self.assertGreater(result.expected_return_pct_20d, 0.0)
        self.assertGreater(result.expected_excess_return_pct_20d, 0.0)
        self.assertGreater(result.forecast_volatility_pct_20d, 0.0)
        self.assertGreater(result.up_probability_20d, result.down_probability_20d)
        self.assertGreaterEqual(result.turnover_pct, 0.0)

        for weight in weights.values():
            self.assertGreaterEqual(weight, 0.0)
            self.assertLessEqual(weight, 34.0 + 0.2)

        kr_weight = weights["005930.KS"] + weights["035420.KS"]
        self.assertLessEqual(kr_weight, 55.0 + 0.2)

        tech_weight = weights["005930.KS"] + weights["AAPL"]
        self.assertLessEqual(tech_weight, 50.0 + 0.2)


if __name__ == "__main__":
    unittest.main()
