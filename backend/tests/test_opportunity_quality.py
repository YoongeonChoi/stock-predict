import unittest

from app.models.forecast import FlowSignal
from app.scoring.opportunity_quality import (
    adjusted_score_with_quality,
    build_sector_quality_context,
    rerank_quote_screen,
    score_opportunity_quality,
)


def _price_bar(day: int, close: float, volume: int) -> dict:
    return {
        "date": f"2026-04-{day + 1:02d}",
        "open": close * 0.995,
        "high": close * 1.012,
        "low": close * 0.988,
        "close": close,
        "volume": volume,
    }


def _orderly_prices() -> list[dict]:
    prices: list[dict] = []
    close = 100.0
    for day in range(40):
        close += 0.28
        prices.append(_price_bar(day, close, 1_000_000 if day < 30 else 1_320_000))
    return prices


def _chase_prices() -> list[dict]:
    prices: list[dict] = []
    close = 100.0
    for day in range(40):
        if day < 35:
            close += 0.18
            volume = 950_000
        else:
            close *= 1.032
            volume = 2_500_000
        prices.append(_price_bar(day, close, volume))
    return prices


class OpportunityQualityTests(unittest.TestCase):
    def test_quote_screen_demotes_one_day_surge_before_detail_scan(self):
        quotes = [
            {"sector": "반도체", "ticker": "CHASE.KS", "current_price": 100, "change_pct": 9.2, "market_cap": 5_000_000_000_000, "volume": 2_800_000, "avg_volume": 1_000_000},
            {"sector": "반도체", "ticker": "ORDERLY.KS", "current_price": 100, "change_pct": 1.9, "market_cap": 5_000_000_000_000, "volume": 1_350_000, "avg_volume": 1_000_000},
            {"sector": "반도체", "ticker": "PEER1.KS", "current_price": 100, "change_pct": 2.4, "market_cap": 4_000_000_000_000, "volume": 1_200_000, "avg_volume": 1_000_000},
            {"sector": "반도체", "ticker": "PEER2.KS", "current_price": 100, "change_pct": 1.1, "market_cap": 3_000_000_000_000, "volume": 1_100_000, "avg_volume": 1_000_000},
        ]

        ranked = rerank_quote_screen(quotes, market_stance="neutral")
        tickers = [item["ticker"] for item in ranked]

        self.assertLess(tickers.index("ORDERLY.KS"), tickers.index("CHASE.KS"))
        self.assertGreater(ranked[tickers.index("CHASE.KS")]["chase_risk_score"], 80.0)
        self.assertGreater(ranked[tickers.index("ORDERLY.KS")]["volume_quality_score"], 55.0)

    def test_quality_score_prefers_orderly_institutional_accumulation(self):
        contexts = build_sector_quality_context(
            [
                {"sector": "반도체", "change_pct": 1.4},
                {"sector": "반도체", "change_pct": 2.1},
                {"sector": "반도체", "change_pct": 0.9},
            ]
        )
        orderly = score_opportunity_quality(
            price_history=_orderly_prices(),
            current_price=_orderly_prices()[-1]["close"],
            change_pct=1.6,
            sector_context=contexts["반도체"],
            flow_signal=FlowSignal(
                available=True,
                source="pykrx",
                market="ORDERLY",
                unit="KRW",
                data_status="fresh_eod",
                foreign_net_buy_1d=200_000_000,
                foreign_net_buy_5d=850_000_000,
                foreign_net_buy_20d=1_800_000_000,
                institutional_net_buy_1d=180_000_000,
                institutional_net_buy_5d=700_000_000,
                institutional_net_buy_20d=1_200_000_000,
                retail_net_buy_1d=-90_000_000,
                retail_net_buy_5d=-300_000_000,
                retail_net_buy_20d=-500_000_000,
                foreign_positive_days_20d=13,
                institutional_positive_days_20d=12,
                retail_positive_days_20d=6,
            ),
        )
        chase = score_opportunity_quality(
            price_history=_chase_prices(),
            current_price=_chase_prices()[-1]["close"],
            change_pct=8.8,
            sector_context=contexts["반도체"],
            flow_signal=FlowSignal(
                available=True,
                source="pykrx",
                market="CHASE",
                unit="KRW",
                data_status="fresh_eod",
                foreign_net_buy_1d=-250_000_000,
                foreign_net_buy_5d=-700_000_000,
                institutional_net_buy_1d=-120_000_000,
                institutional_net_buy_5d=-450_000_000,
                retail_net_buy_1d=500_000_000,
                retail_net_buy_5d=1_400_000_000,
                retail_positive_days_20d=15,
            ),
        )

        self.assertGreater(orderly.quality_score, chase.quality_score)
        self.assertLess(orderly.chase_risk_score, chase.chase_risk_score)
        self.assertEqual(chase.entry_style, "avoid_chase")
        self.assertLessEqual(adjusted_score_with_quality(82.0, chase), 61.0)


if __name__ == "__main__":
    unittest.main()
