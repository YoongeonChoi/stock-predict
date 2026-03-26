import unittest
from datetime import date, timedelta

from app.analysis.free_kr_forecast import build_free_kr_forecast
from app.models.forecast import FlowSignal


def _sample_prices(days: int = 280, daily_drift: float = 0.004, pullback_every: int = 23) -> list[dict]:
    base = date(2025, 1, 2)
    rows = []
    price = 100.0
    for i in range(days):
        drift = daily_drift * (0.45 if i % pullback_every == 0 else 1.0)
        price *= (1.0 + drift)
        high = price * 1.012
        low = price * 0.988
        rows.append(
            {
                "date": (base + timedelta(days=i)).isoformat(),
                "open": round(price * 0.995, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(price, 2),
                "volume": 900_000 + i * 2_200 + (55_000 if i % 11 == 0 else 0),
            }
        )
    return rows


class FreeKrForecastTests(unittest.TestCase):
    def test_forecast_returns_expected_probabilistic_shape(self):
        forecast = build_free_kr_forecast(
            ticker="005930.KS",
            name="테스트전자",
            price_history=_sample_prices(),
            market_history=_sample_prices(daily_drift=0.0025, pullback_every=31),
            google_news=[
                {"title": "테스트전자 수주 확대 기대", "description": "성장과 반등 기대", "published": "2026-03-20"},
                {"title": "테스트전자 실적 개선 전망", "description": "호조 지속", "published": "2026-03-21"},
            ],
            naver_news=[
                {"title": "테스트전자 목표가 상향", "description": "업황 회복", "published": "2026-03-22"},
            ],
            filings=[
                {"report_name": "단일판매ㆍ공급계약체결", "receipt_date": "2026-03-21"},
                {"report_name": "현금ㆍ현물배당결정", "receipt_date": "2026-03-19"},
            ],
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="shares",
                foreign_net_buy=110_000,
                institutional_net_buy=75_000,
                retail_net_buy=-60_000,
            ),
            analyst_context={"buy": 9, "hold": 2, "sell": 1, "target_mean": 148},
            ecos_snapshot={"consumer_sentiment": 101.4, "export_growth": 6.2, "industrial_production": 2.1, "base_rate": 2.75, "cpi_yoy": 2.1},
            kosis_snapshot={"employment": 62.3},
        )

        self.assertIsNotNone(forecast)
        assert forecast is not None
        self.assertEqual(len(forecast.horizons), 3)
        self.assertGreater(len(forecast.evidence), 0)
        self.assertAlmostEqual(sum(forecast.regime_probs.values()), 100.0, places=1)

        for horizon in forecast.horizons:
            self.assertLessEqual(horizon.q10, horizon.q25)
            self.assertLessEqual(horizon.q25, horizon.q50)
            self.assertLessEqual(horizon.q50, horizon.q75)
            self.assertLessEqual(horizon.q75, horizon.q90)
            self.assertAlmostEqual(horizon.p_up + horizon.p_flat + horizon.p_down, 100.0, places=1)
            self.assertGreaterEqual(horizon.confidence, 38.0)
            self.assertLessEqual(horizon.confidence, 88.0)

    def test_bullish_inputs_raise_up_probability_vs_bearish_inputs(self):
        common_kwargs = {
            "ticker": "005930.KS",
            "name": "테스트전자",
            "price_history": _sample_prices(),
            "market_history": _sample_prices(daily_drift=0.0025, pullback_every=31),
            "ecos_snapshot": {"consumer_sentiment": 99.8, "export_growth": 3.0, "industrial_production": 1.0, "base_rate": 2.75, "cpi_yoy": 2.4},
            "kosis_snapshot": {"employment": 61.8},
        }

        bullish = build_free_kr_forecast(
            **common_kwargs,
            google_news=[{"title": "테스트전자 수주 확대", "description": "성장 반등", "published": "2026-03-20"}],
            naver_news=[{"title": "테스트전자 목표가 상향", "description": "strong growth", "published": "2026-03-21"}],
            filings=[{"report_name": "단일판매ㆍ공급계약체결"}],
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="shares",
                foreign_net_buy=120_000,
                institutional_net_buy=90_000,
                retail_net_buy=-40_000,
            ),
            analyst_context={"buy": 10, "hold": 1, "sell": 0, "target_mean": 150},
        )
        bearish = build_free_kr_forecast(
            **common_kwargs,
            google_news=[{"title": "테스트전자 실적 경고", "description": "miss and downgrade", "published": "2026-03-20"}],
            naver_news=[{"title": "테스트전자 목표가 하향", "description": "delay and slowdown", "published": "2026-03-21"}],
            filings=[{"report_name": "유상증자결정"}],
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="shares",
                foreign_net_buy=-130_000,
                institutional_net_buy=-95_000,
                retail_net_buy=70_000,
            ),
            analyst_context={"buy": 1, "hold": 2, "sell": 9, "target_mean": 84},
        )

        assert bullish is not None
        assert bearish is not None
        bullish_5d = next(item for item in bullish.horizons if item.horizon_days == 5)
        bearish_5d = next(item for item in bearish.horizons if item.horizon_days == 5)

        self.assertGreater(bullish_5d.p_up, bearish_5d.p_up)
        self.assertGreater(bullish_5d.mean_return_raw, bearish_5d.mean_return_raw)
        self.assertGreater(bullish_5d.price_q50, bearish_5d.price_q50)


if __name__ == "__main__":
    unittest.main()
