import unittest
from datetime import date, timedelta

from app.analysis.next_day_forecast import forecast_next_day
from app.models.forecast import FlowSignal
from app.utils.market_calendar import next_trading_day


def _sample_prices(days: int = 40) -> list[dict]:
    base = date(2026, 1, 1)
    rows = []
    price = 100.0
    for i in range(days):
        price += 0.8 if i % 6 != 0 else -0.3
        rows.append({
            "date": (base + timedelta(days=i)).isoformat(),
            "open": round(price - 0.6, 2),
            "high": round(price + 1.2, 2),
            "low": round(price - 1.0, 2),
            "close": round(price, 2),
            "volume": 1_000_000 + i * 5_000,
        })
    return rows


class NextDayForecastTests(unittest.TestCase):
    def test_next_trading_day_skips_weekend(self):
        self.assertEqual(next_trading_day("KR", "2026-03-21").isoformat(), "2026-03-23")

    def test_forecast_outputs_expected_structure(self):
        forecast = forecast_next_day(
            ticker="TEST",
            name="Synthetic Corp",
            country_code="KR",
            price_history=_sample_prices(),
            news_items=[
                {"title": "Synthetic Corp beats estimates and raises growth outlook"},
                {"title": "Analysts upgrade Synthetic Corp after resilient demand"},
            ],
            analyst_context={"buy": 8, "hold": 2, "sell": 1, "target_mean": 118},
            flow_signal=FlowSignal(available=False, source="not_supported", market="TEST", unit=""),
            context_bias=0.25,
            asset_type="stock",
        )

        self.assertEqual(forecast.reference_date, _sample_prices()[-1]["date"])
        self.assertGreaterEqual(forecast.predicted_high, max(forecast.predicted_open or 0, forecast.predicted_close))
        self.assertLessEqual(forecast.predicted_low, min(forecast.predicted_open or 0, forecast.predicted_close))
        self.assertTrue(0 <= forecast.up_probability <= 100)
        self.assertTrue(35 <= forecast.confidence <= 92)
        self.assertGreater(len(forecast.drivers), 0)
        self.assertEqual(len(forecast.scenarios), 3)
        self.assertAlmostEqual(sum(item.probability for item in forecast.scenarios), 100.0, places=1)
        self.assertIn(
            forecast.execution_bias,
            {"press_long", "lean_long", "stay_selective", "reduce_risk", "capital_preservation"},
        )
        self.assertTrue(forecast.execution_note)

    def test_short_history_fallback_keeps_scenario_shape(self):
        forecast = forecast_next_day(
            ticker="TEST",
            name="Synthetic Corp",
            country_code="KR",
            price_history=_sample_prices(10),
            asset_type="stock",
        )

        self.assertEqual(forecast.direction, "flat")
        self.assertEqual(len(forecast.scenarios), 3)
        self.assertEqual(forecast.execution_bias, "stay_selective")
        self.assertGreaterEqual(len(forecast.risk_flags), 1)

    def test_bullish_inputs_score_higher_than_bearish_inputs(self):
        bullish = forecast_next_day(
            ticker="TEST",
            name="Synthetic Corp",
            country_code="KR",
            price_history=_sample_prices(),
            news_items=[
                {"title": "Synthetic Corp beats estimates and raises growth outlook"},
                {"title": "Synthetic Corp 상향 and resilient demand surprise"},
            ],
            analyst_context={"buy": 10, "hold": 1, "sell": 0, "target_mean": 121},
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="shares",
                foreign_net_buy=120_000,
                institutional_net_buy=80_000,
                retail_net_buy=-50_000,
            ),
            context_bias=0.4,
            asset_type="stock",
        )

        bearish = forecast_next_day(
            ticker="TEST",
            name="Synthetic Corp",
            country_code="KR",
            price_history=_sample_prices(),
            news_items=[
                {"title": "Synthetic Corp misses estimates and issues warning"},
                {"title": "Synthetic Corp 하향 amid slowdown fears"},
            ],
            analyst_context={"buy": 1, "hold": 3, "sell": 8, "target_mean": 92},
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="shares",
                foreign_net_buy=-130_000,
                institutional_net_buy=-90_000,
                retail_net_buy=70_000,
            ),
            context_bias=-0.4,
            asset_type="stock",
        )

        self.assertGreater(bullish.up_probability, bearish.up_probability)
        self.assertGreater(bullish.predicted_return_pct, bearish.predicted_return_pct)
        self.assertGreater(bullish.news_sentiment, bearish.news_sentiment)
        self.assertGreater(bullish.scenarios[0].price, bearish.scenarios[0].price)


if __name__ == "__main__":
    unittest.main()
