import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from tests.client_helpers import patched_client


class StockRouterTests(unittest.TestCase):
    def test_stock_detail_returns_cached_partial_when_analysis_times_out(self):
        cached_snapshot = {
            "ticker": "005930.KS",
            "name": "삼성전자",
            "country_code": "KR",
            "sector": "Technology",
            "industry": "Hardware",
            "market_cap": 1.0,
            "current_price": 70000,
            "change_pct": 0.5,
            "financials": [],
            "peer_comparisons": [],
            "dividend": {},
            "analyst_ratings": {"buy": 0, "hold": 0, "sell": 0},
            "earnings_history": [],
            "price_history": [],
            "technical": {"ma_20": [], "ma_60": [], "rsi_14": [], "macd": [], "dates": []},
            "score": {
                "total": 50,
                "fundamental": {"total": 10, "items": []},
                "valuation": {"total": 10, "items": []},
                "growth_momentum": {"total": 10, "items": []},
                "analyst": {"total": 10, "items": []},
                "risk": {"total": 10, "items": []},
            },
            "buy_sell_guide": {
                "buy_zone_low": 68000,
                "buy_zone_high": 69000,
                "fair_value": 70000,
                "sell_zone_low": 72000,
                "sell_zone_high": 73000,
                "risk_reward_ratio": 1.0,
                "confidence_grade": "B",
                "methodology": [],
                "summary": "cached",
            },
            "public_summary": {
                "summary": "cached summary",
                "evidence_for": [],
                "evidence_against": [],
                "why_not_buy_now": [],
                "thesis_breakers": [],
                "data_quality": "cached",
                "confidence_note": "cached",
            },
            "generated_at": "2026-03-30T08:00:00+00:00",
            "partial": False,
            "fallback_reason": None,
            "errors": [],
        }

        async def _slow_analysis(*args, **kwargs):
            await asyncio.sleep(0.05)
            return {}

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.STOCK_DETAIL_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=_slow_analysis)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=cached_snapshot)),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_cached_detail")
        self.assertIn("SP-5018", payload["errors"])

    def test_stock_detail_returns_500_when_analysis_fails_without_cache(self):
        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=RuntimeError("boom"))),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["error_code"], "SP-3003")


if __name__ == "__main__":
    unittest.main()
