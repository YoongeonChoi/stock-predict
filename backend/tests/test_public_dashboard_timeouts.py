import asyncio
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from app.routers import country as country_router
from client_helpers import patched_client


async def _slow_response(*args, **kwargs):
    await asyncio.sleep(0.05)
    return {}


async def _slow_list_response(*args, **kwargs):
    await asyncio.sleep(0.05)
    return []


async def _return_fetcher(key, fetcher, ttl=None, **kwargs):
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
            patch("app.routers.country.COUNTRY_REPORT_PUBLIC_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.analyze_country", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._build_country_report_fallback", new=AsyncMock(return_value=fallback_payload)),
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/report")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "country_report_timeout")

    def test_country_report_stale_public_skips_background_refresh_in_render_safe_mode(self):
        archived_payload = {
            "market_summary": "최근 정상 리포트입니다.",
            "top_stocks": [],
        }
        cached_opportunities = AsyncMock(return_value=None)
        cached_quick_opportunities = AsyncMock(return_value=None)
        live_quick_opportunities = AsyncMock(return_value={"opportunities": [], "quote_available_count": 0})
        with (
            patch("app.routers.country._allow_public_background_refresh", return_value=False),
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=archived_payload)),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=cached_opportunities),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=cached_quick_opportunities),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=live_quick_opportunities),
            patch("app.routers.country.get_or_create_background_job") as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/report")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "country_report_stale_public")
        self.assertIn("다음 재조회", response.json()["market_summary"])
        background_job.assert_not_called()
        cached_opportunities.assert_not_awaited()
        cached_quick_opportunities.assert_not_awaited()
        live_quick_opportunities.assert_not_awaited()

    def test_country_report_safe_mode_uses_public_error_code_without_background_job(self):
        with (
            patch("app.routers.country._allow_public_background_refresh", return_value=False),
            patch("app.routers.country.analyze_country", new=AsyncMock(side_effect=RuntimeError("boom"))),
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch(
                "app.routers.country.market_service.get_market_opportunities_quick",
                new=AsyncMock(return_value={"opportunities": [], "quote_available_count": 0}),
            ),
            patch("app.routers.country.get_or_create_background_job") as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/country/KR/report")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "country_report_error")
        self.assertIn("SP-3001", response.json()["errors"])
        self.assertNotIn("SP-5004", response.json()["errors"])
        background_job.assert_not_called()

    def test_market_opportunities_returns_quick_fallback_without_waiting_for_full_timeout(self):
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
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }
        with (
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(return_value={"ok": True})),
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["country_code"], "KR")
        self.assertEqual(response.json()["detailed_scanned_count"], 0)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "opportunity_quick_response")

    def test_market_opportunities_prefers_cached_quick_payload_before_live_refresh(self):
        cached_quick_payload = {
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
            "total_scanned": 120,
            "quote_available_count": 96,
            "detailed_scanned_count": 0,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "krx_listing",
            "universe_note": "이전 quick 응답입니다.",
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }
        with (
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=cached_quick_payload)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(side_effect=AssertionError("live quick should not run"))),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(return_value={"ok": True})),
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "opportunity_cached_quick_response")
        self.assertIn("최근 usable 후보", response.json()["universe_note"])

    def test_market_opportunities_safe_mode_skips_background_refresh(self):
        cached_quick_payload = {
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
            "total_scanned": 120,
            "quote_available_count": 96,
            "detailed_scanned_count": 0,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "krx_listing",
            "universe_note": "이전 quick 응답입니다.",
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }
        with (
            patch("app.routers.country._allow_public_background_refresh", return_value=False),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=cached_quick_payload)),
            patch("app.routers.country.get_or_create_background_job") as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "opportunity_cached_quick_response")
        self.assertIn("다음 재조회", response.json()["universe_note"])
        self.assertNotIn("백그라운드", response.json()["universe_note"])
        background_job.assert_not_called()

    def test_market_opportunities_returns_placeholder_when_quick_times_out_and_no_cache_exists(self):
        placeholder_payload = {
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
                "summary": "정밀 시장 국면 계산이 길어져 현재는 시장 국면만 먼저 표시합니다.",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 243,
            "total_scanned": 0,
            "quote_available_count": 0,
            "detailed_scanned_count": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "universe_source": "fallback",
            "universe_note": "시장 국면만 먼저 표시합니다.",
            "opportunities": [],
        }
        with (
            patch("app.routers.country.OPPORTUNITY_QUICK_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(return_value={"ok": True})),
            patch("app.routers.country.market_service.build_market_opportunities_placeholder", return_value=placeholder_payload),
            patched_client() as client,
        ):
            response = client.get("/api/market/opportunities/KR?limit=8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "opportunity_placeholder_response")
        self.assertEqual(response.json()["total_scanned"], 0)

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

    def test_countries_safe_mode_returns_fallback_and_starts_background_refresh(self):
        background_task = unittest.mock.Mock()
        with (
            patch.object(type(country_router.settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
            patch("app.data.cache.get", new=AsyncMock(side_effect=[None, None])),
            patch("app.data.cache.set", new=AsyncMock()) as cache_set,
            patch("app.routers.country.get_or_create_background_job", return_value=(background_task, True)) as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/countries")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[0]["code"], "KR")
        self.assertEqual(payload[0]["indices"][0]["price"], 0)
        background_job.assert_called_once()
        background_task.add_done_callback.assert_called_once()
        cache_set.assert_awaited_once()

    def test_daily_briefing_timeout_returns_partial_fallback(self):
        fallback_payload = {
            "generated_at": "2026-03-29T09:00:00",
            "partial": True,
            "fallback_reason": "briefing_timeout",
            "market_summary": "브리핑 계산이 길어져 기본 시장 스냅샷을 먼저 표시합니다.",
            "focus_cards": [],
            "upcoming_events": [],
            "news": [],
            "sessions": [],
            "archive_status": {"status": "partial"},
            "priorities": ["기본 시장 스냅샷 먼저 표시"],
        }
        with (
            patch("app.routers.briefing.PUBLIC_ENDPOINT_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.briefing.briefing_service.get_daily_briefing", new=AsyncMock(side_effect=_slow_response)),
            patch("app.routers.briefing.briefing_service.get_daily_briefing_fallback", new=AsyncMock(return_value=fallback_payload)),
            patched_client() as client,
        ):
            response = client.get("/api/briefing/daily")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "briefing_timeout")

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
        self.assertEqual(response.json()["fallback_reason"], "kr_bulk_snapshot_only")
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
        representative_quotes = AsyncMock(
            return_value={
                "000001.KS": {
                    "ticker": "000001.KS",
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
                "app.routers.screener.kr_market_quote_client.get_kr_representative_quotes",
                new=representative_quotes,
            ),
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "kr_representative_snapshot_warming")
        representative_quotes.assert_awaited_once_with(limit=20)
        warmup.assert_called_once()

    def test_screener_default_kr_path_falls_back_to_bulk_partial_when_representative_quotes_are_empty(self):
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
                "app.routers.screener.kr_market_quote_client.get_kr_representative_quotes",
                new=AsyncMock(return_value={}),
            ),
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

    def test_screener_partial_does_not_schedule_cache_warmup_in_render_safe_mode(self):
        sector_map = {
            f"Sector {index}": [f"{index:06d}.KS"]
            for index in range(1, 13)
        }
        representative_quotes = AsyncMock(
            return_value={
                "000001.KS": {
                    "ticker": "000001.KS",
                    "name": "Samsung Electronics",
                    "current_price": 70100.0,
                    "prev_close": 69300.0,
                    "market_cap": 420000000000.0,
                    "change_pct": 1.15,
                }
            }
        )
        with (
            patch("app.routers.screener._allow_public_screener_warmup", return_value=False),
            patch("app.routers.screener.cache.get", new=AsyncMock(return_value=None)),
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value=sector_map)),
            patch(
                "app.routers.screener.kr_market_quote_client.get_kr_representative_quotes",
                new=representative_quotes,
            ),
            patch("app.routers.screener.get_or_create_background_job") as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["partial"])
        self.assertEqual(response.json()["fallback_reason"], "kr_representative_snapshot_warming")
        background_job.assert_not_called()

    def test_screener_safe_mode_returns_shell_response_when_representative_path_times_out(self):
        sector_map = {
            f"Sector {index}": [f"{index:06d}.KS"]
            for index in range(1, 13)
        }
        background_task = unittest.mock.Mock()
        with (
            patch.object(type(country_router.settings), "startup_memory_safe_mode", new_callable=PropertyMock, return_value=True),
            patch("app.routers.screener.PUBLIC_SCREENER_PARTIAL_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.screener.cache.get", new=AsyncMock(side_effect=[None, None])),
            patch("app.routers.screener.cache.set", new=AsyncMock()) as cache_set,
            patch("app.routers.screener.get_universe", new=AsyncMock(return_value=sector_map)),
            patch(
                "app.routers.screener._build_kr_representative_snapshot_results",
                new=AsyncMock(side_effect=_slow_list_response),
            ),
            patch("app.routers.screener.get_or_create_background_job", return_value=(background_task, True)) as background_job,
            patched_client() as client,
        ):
            response = client.get("/api/screener?country=KR&limit=20")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "kr_safe_shell_warming")
        self.assertEqual(payload["results"][0]["current_price"], 0.0)
        background_job.assert_called_once()
        self.assertGreaterEqual(cache_set.await_count, 1)


if __name__ == "__main__":
    unittest.main()
