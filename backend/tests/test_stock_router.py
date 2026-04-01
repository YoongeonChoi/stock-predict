import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tests.client_helpers import patched_client


def _cached_snapshot(*, partial: bool = False, fallback_reason: str | None = None, errors: list[str] | None = None):
    return {
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
        "partial": partial,
        "fallback_reason": fallback_reason,
        "errors": errors or [],
    }


class StockRouterTests(unittest.TestCase):
    def test_stock_detail_returns_cached_full_immediately_when_available(self):
        cached_full = _cached_snapshot()

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=cached_full)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=None)),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["partial"])
        self.assertIsNone(payload["fallback_reason"])
        self.assertEqual(payload["errors"], [])

    def test_stock_detail_returns_quick_partial_when_quick_cache_exists(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=True)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertEqual(payload["errors"], [])

    def test_stock_detail_returns_cached_quick_partial_when_quick_builder_times_out(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_quick(*args, **kwargs):
            await asyncio.sleep(0.05)
            return quick_snapshot

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=True)),
            patch("app.routers.stock.STOCK_DETAIL_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch(
                "app.routers.stock.get_cached_quick_stock_detail",
                new=AsyncMock(side_effect=[None, quick_snapshot]),
            ),
            patch("app.routers.stock.build_quick_stock_detail", new=AsyncMock(side_effect=_slow_quick)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertIn("SP-5018", payload["errors"])

    def test_stock_detail_prefer_full_returns_cached_quick_partial_when_upgrade_grace_times_out(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_full(*args, **kwargs):
            await asyncio.sleep(0.05)
            return _cached_snapshot(partial=False, fallback_reason=None)

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False)),
            patch("app.routers.stock.STOCK_DETAIL_FULL_UPGRADE_GRACE_SECONDS", 0.01),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=_slow_full)) as analyze_stock,
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()) as schedule_refresh,
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertIn("SP-5018", payload["errors"])
        analyze_stock.assert_awaited()
        schedule_refresh.assert_not_called()

    def test_stock_detail_prefer_full_returns_fresh_quick_partial_without_waiting_for_full(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_full(*args, **kwargs):
            await asyncio.sleep(0.05)
            return _cached_snapshot(partial=False, fallback_reason=None)

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False)),
            patch("app.routers.stock.STOCK_DETAIL_FULL_UPGRADE_GRACE_SECONDS", 0.01),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.build_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=_slow_full)) as analyze_stock,
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()) as schedule_refresh,
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertIn("SP-5018", payload["errors"])
        analyze_stock.assert_awaited()
        schedule_refresh.assert_not_called()

    def test_stock_detail_prefer_full_returns_full_when_quick_snapshot_is_unavailable(self):
        full_snapshot = _cached_snapshot(partial=False, fallback_reason=None)
        full_snapshot["generated_at"] = "2026-03-30T08:15:00+00:00"

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.build_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(return_value=full_snapshot)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()) as schedule_refresh,
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["partial"])
        self.assertIsNone(payload["fallback_reason"])
        schedule_refresh.assert_not_called()

    def test_stock_detail_returns_500_when_quick_and_full_fail_without_cache(self):
        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.build_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload["error_code"], "SP-3003")


if __name__ == "__main__":
    unittest.main()
