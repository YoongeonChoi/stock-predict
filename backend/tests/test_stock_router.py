import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.analysis.stock_cache_keys import stock_detail_latest_cache_key, stock_detail_quick_cache_key
from app.routers import stock as stock_router
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
    def test_build_stock_success_response_defers_memory_trim_until_background_task(self):
        payload = _cached_snapshot()

        with patch("app.routers.stock._maybe_trim_public_route_memory") as trim:
            response = stock_router._build_stock_success_response(payload, trim_reason="stock_detail")

            trim.assert_not_called()
            self.assertIsNotNone(response.background)
            asyncio.run(response.background())

        trim.assert_called_once_with("stock_detail")

    def test_get_cached_stock_detail_without_refresh_uses_lightweight_cache(self):
        cached = _cached_snapshot()

        with patch("app.routers.stock.cache.get", new=AsyncMock(return_value=cached)) as cache_get:
            result = asyncio.run(stock_router.get_cached_stock_detail("005930.KS"))

        cache_get.assert_awaited_once_with(stock_detail_latest_cache_key("005930.KS"))
        self.assertEqual(result["ticker"], "005930.KS")
        self.assertIsNot(result, cached)

    def test_get_cached_quick_stock_detail_uses_lightweight_cache(self):
        cached = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        with patch("app.routers.stock.cache.get", new=AsyncMock(return_value=cached)) as cache_get:
            result = asyncio.run(stock_router.get_cached_quick_stock_detail("005930.KS"))

        cache_get.assert_awaited_once_with(stock_detail_quick_cache_key("005930.KS"))
        self.assertEqual(result["fallback_reason"], "stock_quick_detail")
        self.assertIsNot(result, cached)

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
            patch("app.routers.stock.prediction_capture_service.schedule_stock_distributional_capture", new=AsyncMock(return_value=True)),
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

    def test_stock_detail_cached_full_skips_inline_prediction_capture(self):
        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=_cached_snapshot())),
            patch("app.routers.stock.prediction_capture_service.capture_report_predictions", new=AsyncMock(side_effect=AssertionError("cached full response should not capture inline"))),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["partial"])

    def test_stock_detail_quick_path_skips_inline_prediction_capture(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=True, startup_memory_safe_mode=False)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.prediction_capture_service.capture_report_predictions", new=AsyncMock(side_effect=AssertionError("quick response should not capture inline"))),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")

    def test_stock_detail_skips_slow_cache_lookups_and_uses_quick_path(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_cached(*args, **kwargs):
            await asyncio.sleep(0.05)
            return _cached_snapshot()

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.STOCK_DETAIL_CACHE_LOOKUP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=True, startup_memory_safe_mode=False)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(side_effect=_slow_cached)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")

    def test_stock_detail_prefer_full_records_full_trace_when_cached_quick_upgrades_successfully(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")
        full_snapshot = _cached_snapshot(partial=False, fallback_reason=None)
        full_snapshot["generated_at"] = "2026-03-30T08:15:00+00:00"

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False)),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(return_value=full_snapshot)),
            patch("app.routers.stock._record_stock_detail_trace") as record_trace,
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["partial"])
        self.assertIsNone(payload["fallback_reason"])
        record_trace.assert_called_once()
        self.assertEqual(record_trace.call_args.kwargs["request_phase"], "full")
        self.assertEqual(record_trace.call_args.kwargs["cache_state"], "sqlite_hit")

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

    def test_stock_detail_quick_path_timeboxes_distributional_capture_scheduling(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_schedule(*args, **kwargs):
            await asyncio.sleep(0.2)
            return True

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=True, startup_memory_safe_mode=False)),
            patch("app.routers.stock.STOCK_DISTRIBUTIONAL_CAPTURE_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.prediction_capture_service.schedule_stock_distributional_capture", new=AsyncMock(side_effect=_slow_schedule)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            started_at = time.perf_counter()
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail")
            elapsed = time.perf_counter() - started_at

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertLess(elapsed, 0.08)

    def test_stock_detail_prefer_full_timeout_does_not_wait_for_cancellation_cleanup(self):
        quick_snapshot = _cached_snapshot(partial=True, fallback_reason="stock_quick_detail")

        async def _slow_full(*args, **kwargs):
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                await asyncio.sleep(0.2)
                raise

        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False, startup_memory_safe_mode=False)),
            patch("app.routers.stock.STOCK_DETAIL_FULL_UPGRADE_GRACE_SECONDS", 0.01),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=quick_snapshot)),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=_slow_full)),
            patch("app.routers.stock.prediction_capture_service.schedule_stock_distributional_capture", new=AsyncMock(return_value=True)),
            patch("app.routers.stock._schedule_stock_detail_refresh", new=MagicMock()),
        ):
            started_at = time.perf_counter()
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")
            elapsed = time.perf_counter() - started_at

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_quick_detail")
        self.assertLess(elapsed, 0.08)

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

    def test_stock_detail_returns_memory_guard_shell_without_invoking_heavy_builders(self):
        with (
            patch("app.routers.stock._resolve_kr_ticker", return_value="005930.KS"),
            patch("app.routers.stock.settings", new=SimpleNamespace(effective_stock_detail_background_refresh=False, startup_memory_safe_mode=True)),
            patch("app.routers.stock.get_memory_pressure_snapshot", return_value={"pressure_ratio": 0.86}),
            patch("app.routers.stock.get_cached_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.get_cached_quick_stock_detail", new=AsyncMock(return_value=None)),
            patch("app.routers.stock.build_quick_stock_detail", new=AsyncMock(side_effect=AssertionError("quick builder should be skipped"))),
            patch("app.routers.stock.analyze_stock", new=AsyncMock(side_effect=AssertionError("full analyzer should be skipped"))),
            patch("app.routers.stock.ticker_resolver_service.get_ticker_metadata", return_value={"country_code": "KR", "sector": "Information Technology"}),
            patch("app.routers.stock.cache.set", new=AsyncMock(return_value=None)),
        ):
            with patched_client() as client:
                response = client.get("/api/stock/005930/detail?prefer_full=true")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "stock_memory_guard")
        self.assertEqual(payload["name"], "005930.KS")
        self.assertEqual(payload["current_price"], 0.0)
        self.assertEqual(payload["public_summary"]["data_quality"], "티커·기본 메타데이터 중심 최소 응답")

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
