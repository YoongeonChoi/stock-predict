import unittest

from app.analysis.chart_setup import build_short_horizon_chart_analysis
from app.analysis.stock_analyzer import _calc_technicals
from app.models.stock import PricePoint


def _price_bar(day: int, close: float, volume: int) -> dict:
    return {
        "date": f"2026-02-{(day % 28) + 1:02d}",
        "open": round(close - 0.5, 2),
        "high": round(close + 1.0, 2),
        "low": round(close - 1.1, 2),
        "close": round(close, 2),
        "volume": volume,
    }


def _orderly_breakout_prices() -> list[dict]:
    prices: list[dict] = []
    close = 100.0
    for day in range(60):
        close += 0.35
        if day >= 50:
            close += 0.15
        volume = 1_000_000 if day < 52 else 1_450_000
        prices.append(_price_bar(day, close, volume))
    return prices


def _overextended_chase_prices() -> list[dict]:
    prices: list[dict] = []
    close = 100.0
    for day in range(60):
        if day < 54:
            close += 0.28
            volume = 1_000_000
        else:
            close *= 1.025
            volume = 880_000
        prices.append(_price_bar(day, close, volume))
    return prices


class ChartSetupTests(unittest.TestCase):
    def test_chart_analysis_prefers_orderly_breakout_over_chasing_extension(self):
        orderly_prices = _orderly_breakout_prices()
        extended_prices = _overextended_chase_prices()

        orderly = build_short_horizon_chart_analysis(
            price_history=[PricePoint(**item) for item in orderly_prices],
            technical=_calc_technicals(orderly_prices),
            current_price=orderly_prices[-1]["close"],
        )
        extended = build_short_horizon_chart_analysis(
            price_history=[PricePoint(**item) for item in extended_prices],
            technical=_calc_technicals(extended_prices),
            current_price=extended_prices[-1]["close"],
        )

        self.assertGreater(orderly.score, extended.score)
        self.assertGreater(orderly.score, 60.0)
        self.assertGreaterEqual(len(extended.caution_flags), 1)

    def test_chart_analysis_marks_overextended_setup_as_stand_aside_or_pullback(self):
        prices = _overextended_chase_prices()
        analysis = build_short_horizon_chart_analysis(
            price_history=[PricePoint(**item) for item in prices],
            technical=_calc_technicals(prices),
            current_price=prices[-1]["close"],
        )

        self.assertIn(analysis.entry_style, {"stand_aside", "pullback"})
        self.assertTrue(
            any("과열" in flag or "추격" in flag or "상단" in flag for flag in analysis.caution_flags),
            analysis.caution_flags,
        )
