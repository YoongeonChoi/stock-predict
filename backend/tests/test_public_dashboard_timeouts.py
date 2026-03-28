import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.routers import country as country_router
from client_helpers import patched_client


async def _slow_response(*args, **kwargs):
    await asyncio.sleep(0.05)
    return {}


async def _return_fetcher(key, fetcher, ttl=None):
    return await fetcher()


class PublicDashboardTimeoutTests(unittest.TestCase):
    def test_country_report_timeout_returns_partial_fallback(self):
        fallback_payload = {
            "country": {"code": "KR"},
            "partial": True,
            "fallback_reason": "country_report_timeout",
            "errors": ["SP-5018"],
        }
        with (
            patch("app.routers.country.PUBLIC_ENDPOINT_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.analyze_country", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country._build_country_report_fallback", new=AsyncMock(return_value=fallback_payload)),
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/report")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "country_report_timeout")

    def test_market_opportunities_timeout_returns_quick_fallback(self):
        quick_payload = {
            "country_code": "KR",
            "generated_at": "2026-03-27T12:00:00",
            "market_regime": {
                "label": "KR 빠른 스냅샷",
                "stance": "neutral",
                "trend": "range",
                "volatility": "normal",
                "breadth": "mixed",
                "score": 50.0,
                "conviction": 38.0,
                "summary": "정밀 시장 국면 계산이 길어져 1차 시세 스캔 후보를 먼저 제공합니다.",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 2729,
            "total_scanned": 2729,
            "quote_available_count": 2700,
            "detailed_scanned_count": 0,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "krx_listing",
            "universe_note": "상세 분포 계산이 길어져 1차 시세 스캔 후보를 먼저 반환합니다.",
            "opportunities": [],
        }
        with (
            patch("app.routers.country.OPPORTUNITY_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["country_code"], "KR")
        self.assertEqual(response.json()["detailed_scanned_count"], 0)

    def test_heatmap_timeout_returns_partial_fallback(self):
        with (
            patch("app.routers.country.HEATMAP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country._build_heatmap_payload", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country._build_heatmap_fallback", new=AsyncMock(return_value={"children": [], "partial": True})),
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/heatmap")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])

    def test_heatmap_skips_cancelled_items_from_snapshot_gather(self):
        with (
            patch("app.data.universe_data.get_universe", new=AsyncMock(return_value={"Information Technology": ["005930.KS"]})),
            patch("app.routers.country.gather_limited", new=AsyncMock(return_value=[asyncio.CancelledError(), None, {"ticker": "005930.KS", "name": "Samsung Electronics", "market_cap": 420000000000.0, "change_pct": 1.5}])),
        ):
            response = asyncio.run(country_router._build_heatmap_payload("KR"))

        self.assertIn("children", response)

    def test_daily_briefing_timeout_returns_structured_error(self):
        with (
            patch("app.routers.briefing.PUBLIC_ENDPOINT_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.briefing.briefing_service.get_daily_briefing", new=AsyncMock(side_effect=_slow_response)),
            patched_client() as client,
        ):
            response = client.get("/api/briefing/daily")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error_code"], "SP-5018")

    def test_screener_timeout_returns_snapshot_fallback(self):
        async def _slow_gather(*args, **kwargs):
            await asyncio.sleep(0.05)
            return []

        bulk_quotes = AsyncMock(
            return_value={
                "005930.KS": {
                    "ticker": "005930.KS",
                    "name": "Samsung Electronics",
                    "current_price": 70000.0,
                    "prev_close": 68900.0,
                    "market_cap": 420000000000.0,
                    "change_pct": 1.6,
                }
            }
        )
        with (
            patch("app.routers.screener.PUBLIC_SCREENER_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.screener.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value={"Information Technology": ["005930.KS"]})),
            patch("app.routers.screener.gather_limited", new=AsyncMock(side_effect=_slow_gather)),
            patch(
                "app.routers.screener.kr_market_quote_client.get_kr_bulk_quotes",
                new=bulk_quotes,
            ),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&score_min=60")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        bulk_quotes.assert_awaited_once_with(["005930.KS"], skip_full_market_fallback=True)

    def test_screener_default_kr_path_uses_bulk_quotes(self):
        bulk_quotes = AsyncMock(
            return_value={
                "005930.KS": {
                    "ticker": "005930.KS",
                    "name": "Samsung Electronics",
                    "current_price": 70100.0,
                    "prev_close": 69300.0,
                    "market_cap": 420000000000.0,
                    "change_pct": 1.15,
                }
            }
        )
        with (
            patch(
                "app.routers.screener.cache.get_or_fetch",
                new=AsyncMock(side_effect=AssertionError("default KR screener should bypass shared cache")),
            ),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value={"Information Technology": ["005930.KS"]})),
            patch(
                "app.routers.screener.kr_market_quote_client.get_kr_bulk_quotes",
                new=bulk_quotes,
            ),
            patch(
                "app.routers.screener.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=AssertionError("default KR screener should use bulk quotes")),
            ),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["results"][0]["ticker"], "005930.KS")
        bulk_quotes.assert_awaited_once_with(["005930.KS"], skip_full_market_fallback=True)

    def test_screener_default_kr_path_caps_candidates_to_limit_floor(self):
        sector_map = {
            f"Sector {index}": [f"{index:06d}.KS"]
            for index in range(1, 13)
        }
        expected_tickers = [f"{index:06d}.KS" for index in range(1, 11)]
        bulk_quotes = AsyncMock(
            return_value={
                expected_tickers[0]: {
                    "ticker": expected_tickers[0],
                    "name": "Samsung Electronics",
                    "current_price": 70100.0,
                    "prev_close": 69300.0,
                    "market_cap": 420000000000.0,
                    "change_pct": 1.15,
                }
            }
        )
        with (
            patch(
                "app.routers.screener.cache.get_or_fetch",
                new=AsyncMock(side_effect=AssertionError("default KR screener should bypass shared cache")),
            ),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value=sector_map)),
            patch(
                "app.routers.screener.kr_market_quote_client.get_kr_bulk_quotes",
                new=bulk_quotes,
            ),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=1")

        self.assertEqual(response.status_code, 200)
        bulk_quotes.assert_awaited_once_with(expected_tickers, skip_full_market_fallback=True)

    def test_screener_default_kr_path_returns_partial_while_cache_warms(self):
        sector_map = {
            f"Sector {index}": [f"{index:06d}.KS"]
            for index in range(1, 13)
        }
        expected_tickers = [f"{index:06d}.KS" for index in range(1, 11)]
        bulk_quotes = AsyncMock(
            return_value={
                expected_tickers[0]: {
                    "ticker": expected_tickers[0],
                    "name": "Samsung Electronics",
                    "current_price": 70100.0,
                    "prev_close": 69300.0,
                    "market_cap": 420000000000.0,
                    "change_pct": 1.15,
                }
            }
        )
        with (
            patch("app.routers.screener.cache.get", new=AsyncMock(return_value=None)),
            patch("app.routers.screener._spawn_screener_cache_warmup") as warmup,
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value=sector_map)),
            patch(
                "app.routers.screener.kr_market_quote_client.get_kr_bulk_quotes",
                new=bulk_quotes,
            ),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "kr_bulk_snapshot_warming")
        bulk_quotes.assert_awaited_once_with(expected_tickers, skip_full_market_fallback=True)
        warmup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
