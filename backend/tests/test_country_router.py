import asyncio
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers import country
from app.runtime import reset_runtime_state


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_runtime_state()

    async def test_build_country_success_response_defers_memory_trim_until_background_task(self):
        payload = {"country": {"code": "KR"}, "market_summary": "ok"}

        with patch("app.routers.country._maybe_trim_public_route_memory") as trim:
            response = country._build_country_success_response(payload, trim_reason="country_report")

            trim.assert_not_called()
            self.assertIsNotNone(response.background)
            await response.background()

        trim.assert_called_once_with("country_report")

    async def test_market_opportunities_returns_quick_and_starts_background_refresh(self):
        refresh_started = asyncio.Event()
        quick_payload = {
            "country_code": "KR",
            "generated_at": "2026-03-27T12:00:00",
            "market_regime": None,
            "universe_size": 201,
            "total_scanned": 201,
            "quote_available_count": 180,
            "detailed_scanned_count": 0,
            "actionable_count": 6,
            "bullish_count": 4,
            "universe_source": "fallback",
            "universe_note": "기본 종목군 quick fallback",
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }

        async def slow_builder(*args, **kwargs):
            refresh_started.set()
            await asyncio.sleep(0.03)
            return {"country_code": "KR", "opportunities": []}

        with (
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_market_opportunities", new=AsyncMock(side_effect=slow_builder)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertEqual(response["country_code"], "KR")
        self.assertEqual(response["detailed_scanned_count"], 0)
        self.assertIn("quick fallback", response["universe_note"])
        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "opportunity_quick_response")
        await asyncio.wait_for(refresh_started.wait(), timeout=0.2)

    async def test_market_opportunities_uses_cached_quick_snapshot_with_trace(self):
        quick_payload = {
            "country_code": "KR",
            "generated_at": "2026-03-27T12:00:00",
            "market_regime": None,
            "universe_size": 201,
            "total_scanned": 201,
            "quote_available_count": 180,
            "detailed_scanned_count": 0,
            "actionable_count": 6,
            "bullish_count": 4,
            "universe_source": "fallback",
            "universe_note": "cached quick payload",
            "opportunities": [{"ticker": "005930.KS", "action": "accumulate"}],
        }

        with (
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=quick_payload)),
            patch("app.routers.country._spawn_opportunity_refresh", new=MagicMock()) as spawn_refresh,
            patch("app.routers.country.route_stability_service.record_route_trace") as record_trace,
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "opportunity_cached_quick_response")
        self.assertEqual(response["fallback_tier"], "cached_quick")
        spawn_refresh.assert_called_once_with("KR", 12)
        record_trace.assert_called_once()
        self.assertEqual(record_trace.call_args.args[0], "market_opportunities")
        self.assertEqual(record_trace.call_args.args[1]["request_phase"], "quick")
        self.assertEqual(record_trace.call_args.args[1]["cache_state"], "sqlite_hit")

    async def test_spawn_opportunity_refresh_reuses_existing_background_job(self):
        first_started = asyncio.Event()
        release_refresh = asyncio.Event()

        async def slow_builder(*args, **kwargs):
            first_started.set()
            await release_refresh.wait()
            return {"country_code": "KR", "opportunities": []}

        refresh_builder = AsyncMock(side_effect=slow_builder)

        with patch("app.routers.country.market_service.get_market_opportunities", new=refresh_builder):
            country._spawn_opportunity_refresh("KR", 17)
            await asyncio.wait_for(first_started.wait(), timeout=0.2)
            country._spawn_opportunity_refresh("KR", 17)
            await asyncio.sleep(0.01)
            self.assertEqual(refresh_builder.await_count, 1)
            release_refresh.set()
            await asyncio.sleep(0.01)

    async def test_list_countries_returns_fallback_when_payload_times_out(self):
        async def _slow_payload():
            await asyncio.sleep(0.03)
            return []

        async def _return_fetcher(_key, fetcher, ttl=None, **kwargs):
            return await fetcher()

        with (
            patch("app.routers.country.COUNTRIES_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country._build_countries_payload", new=AsyncMock(side_effect=_slow_payload)),
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
        ):
            response = await country.list_countries()

        self.assertTrue(response)
        self.assertEqual(response[0]["indices"][0]["price"], 0)
        self.assertEqual(response[0]["indices"][0]["change_pct"], 0)

    async def test_list_countries_safe_mode_reuses_last_success_without_spawning_refresh(self):
        last_success = [
            {
                "code": "KR",
                "name": "South Korea",
                "name_local": "한국",
                "currency": "KRW",
                "indices": [{"ticker": "^KS11", "name": "KOSPI", "price": 2712.3, "change_pct": 0.8}],
            }
        ]

        with (
            patch("app.routers.country.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch("app.data.cache.get", new=AsyncMock(side_effect=[None, last_success])),
            patch("app.data.cache.set", new=AsyncMock()) as cache_set,
            patch(
                "app.routers.country.get_or_create_background_job",
                side_effect=AssertionError("safe mode should not spawn countries refresh"),
            ),
        ):
            response = await country.list_countries()

        self.assertEqual(response, last_success)
        cache_set.assert_not_awaited()

    async def test_list_countries_safe_mode_seeds_fallback_without_spawning_refresh(self):
        with (
            patch("app.routers.country.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch("app.data.cache.get", new=AsyncMock(side_effect=[None, None])),
            patch("app.data.cache.set", new=AsyncMock()) as cache_set,
            patch(
                "app.routers.country.get_or_create_background_job",
                side_effect=AssertionError("safe mode should not spawn countries refresh"),
            ),
        ):
            response = await country.list_countries()

        self.assertTrue(response)
        self.assertEqual(response[0]["indices"][0]["price"], 0)
        cache_set.assert_awaited_once()

    async def test_market_movers_prefers_kr_representative_quotes(self):
        representative_quotes = {
            "005930.KS": {
                "ticker": "005930.KS",
                "name": "Samsung Electronics",
                "current_price": 71200.0,
                "change_pct": 2.4,
            },
            "000660.KS": {
                "ticker": "000660.KS",
                "name": "SK hynix",
                "current_price": 182000.0,
                "change_pct": -1.2,
            },
        }

        async def _return_fetcher(_key, fetcher, ttl=None, **kwargs):
            return await fetcher()

        with (
            patch("app.data.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.routers.country.kr_market_quote_client.get_kr_representative_quotes",
                new=AsyncMock(return_value=representative_quotes),
            ) as representative_loader,
            patch(
                "app.data.universe_data.get_universe",
                new=AsyncMock(side_effect=AssertionError("KR representative quotes should avoid the universe fallback")),
            ),
        ):
            response = await country.get_market_movers("KR")

        self.assertEqual(response["gainers"][0]["ticker"], "005930.KS")
        self.assertEqual(response["losers"][0]["ticker"], "000660.KS")
        representative_loader.assert_awaited_once()

    async def test_heatmap_fallback_prefers_representative_quotes(self):
        representative_quotes = {
            "005930.KS": {
                "ticker": "005930.KS",
                "name": "Samsung Electronics",
                "current_price": 71200.0,
                "change_pct": 2.4,
                "market_cap": 420000000000.0,
            },
            "000660.KS": {
                "ticker": "000660.KS",
                "name": "SK hynix",
                "current_price": 182000.0,
                "change_pct": -1.2,
                "market_cap": 130000000000.0,
            },
        }

        with (
            patch("app.data.universe_data.get_universe", new=AsyncMock(return_value={"Information Technology": ["005930.KS", "000660.KS"]})),
            patch("app.routers.country._load_cached_kr_representative_quotes", new=AsyncMock(return_value=representative_quotes)),
        ):
            response = await country._build_heatmap_fallback("KR")

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "live_snapshot_timeout")
        self.assertEqual(response["children"][0]["children"][0]["ticker"], "005930.KS")
        self.assertNotEqual(response["children"][0]["children"][0]["change"], 0.0)

    async def test_country_report_fallback_uses_latest_archived_report(self):
        archived_report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "이전 정상 리포트입니다.",
            "key_news": [{"title": "테스트 기사", "source": "연합뉴스", "url": "https://example.com", "published": "2026-04-04"}],
            "top_stocks": [{"ticker": "005930.KS", "name": "삼성전자", "score": 78.5, "change_pct": 1.4, "reason": "실적 회복 기대"}],
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.4}},
            "errors": [],
        }

        with (
            patch("app.routers.country.archive_service.list_reports", new=AsyncMock(return_value=[{"id": 7}])),
            patch("app.routers.country.archive_service.get_report", new=AsyncMock(return_value={"report_json": archived_report})),
            patch("app.data.cache.get", new=AsyncMock(return_value=[{"code": "KR", "indices": [{"price": 2550.0, "change_pct": 0.8}]}])),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(return_value={"opportunities": []})),
        ):
            response = await country._build_country_report_fallback(
                "KR",
                reason="country_report_timeout",
                error_code="SP-5018",
                detail="실시간 계산이 지연되고 있습니다.",
            )

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "country_report_timeout")
        self.assertEqual(response["key_news"][0]["title"], "테스트 기사")
        self.assertIn("최근 정상 리포트", response["market_summary"])
        self.assertEqual(response["market_data"]["KOSPI"]["price"], 2550.0)
        self.assertIn("SP-5018", response["errors"])

    async def test_country_report_fallback_skips_quick_candidates_when_archive_already_has_top_stocks(self):
        archived_report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "이전 정상 리포트입니다.",
            "key_news": [],
            "top_stocks": [{"ticker": "005930.KS", "name": "삼성전자", "score": 78.5, "change_pct": 1.4, "reason": "실적 회복 기대"}],
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.4}},
            "errors": [],
        }

        with (
            patch("app.routers.country.archive_service.list_reports", new=AsyncMock(return_value=[{"id": 7}])),
            patch("app.routers.country.archive_service.get_report", new=AsyncMock(return_value={"report_json": archived_report})),
            patch("app.data.cache.get", new=AsyncMock(return_value=[{"code": "KR", "indices": [{"price": 2550.0, "change_pct": 0.8}]}])),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(side_effect=AssertionError("quick candidate lookup should be skipped"))),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(side_effect=AssertionError("quick candidate lookup should be skipped"))),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(side_effect=AssertionError("quick candidate lookup should be skipped"))),
        ):
            response = await country._build_country_report_fallback(
                "KR",
                reason="country_report_timeout",
                error_code="SP-5018",
                detail="실시간 계산이 지연되고 있습니다.",
            )

        self.assertTrue(response["partial"])
        self.assertEqual(response["top_stocks"][0]["ticker"], "005930.KS")

    async def test_get_country_report_prefers_cached_last_success_and_starts_refresh(self):
        cached_report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "최근 정상 캐시 리포트입니다.",
            "macro_claims": [],
            "key_news": [],
            "institutional_analysis": {"policy_institutions": [], "sell_side": [], "policy_sellside_aligned": False, "consensus_count": 0, "consensus_summary": ""},
            "top_stocks": [],
            "fear_greed": {"value": 50.0, "label": "neutral", "summary": ""},
            "forecast": {"index_ticker": "KS11", "index_name": "KOSPI", "current_price": 1.0, "fair_value": 1.0, "scenarios": [], "confidence_note": ""},
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.1}},
            "generated_at": "2026-04-10T09:00:00",
        }

        with (
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=cached_report)),
            patch("app.routers.country._spawn_country_report_refresh") as spawn_refresh,
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(side_effect=AssertionError("slow path should be skipped"))),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(payload["market_summary"], "최근 정상 캐시 리포트입니다.")
        spawn_refresh.assert_called_once_with("KR")

    async def test_get_country_report_prefers_archived_response_before_waiting_for_slow_refresh(self):
        fallback_payload = {
            "country": {"code": "KR"},
            "market_summary": "최근 정상 리포트를 먼저 제공합니다.",
            "partial": True,
            "fallback_reason": "country_report_stale_public",
            "errors": [],
        }

        with (
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value={"country": {"code": "KR"}})),
            patch("app.routers.country._spawn_country_report_refresh") as spawn_refresh,
            patch("app.routers.country._build_country_report_fallback", new=AsyncMock(return_value=fallback_payload)),
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(side_effect=AssertionError("slow path should be skipped"))),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "country_report_stale_public")
        spawn_refresh.assert_called_once_with("KR")

    async def test_download_country_report_csv_uses_export_timeout_budget(self):
        report = {"country": {"code": "KR"}, "market_summary": "summary"}

        with (
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(return_value=(report, False))) as loader,
            patch("app.routers.country.export_service.export_csv", return_value="country\nKR\n"),
        ):
            response = await country.download_country_report_csv("KR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(loader.await_args.kwargs["timeout_seconds"], country.COUNTRY_REPORT_EXPORT_TIMEOUT_SECONDS)
        self.assertFalse(loader.await_args.kwargs["keep_background"])

    async def test_country_report_sanitizes_non_finite_floats(self):
        report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "score": {"total": float("nan")},
            "market_summary": "summary",
            "macro_claims": [],
            "key_news": [],
            "institutional_analysis": {"policy_institutions": [], "sell_side": [], "policy_sellside_aligned": False, "consensus_count": 0, "consensus_summary": ""},
            "top_stocks": [],
            "fear_greed": {"value": float("inf"), "label": "neutral", "summary": ""},
            "forecast": {"index_ticker": "KS11", "index_name": "KOSPI", "current_price": 1.0, "fair_value": float("-inf"), "scenarios": [], "confidence_note": ""},
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": float("nan")}},
            "generated_at": "2026-04-04T00:00:00",
        }

        with (
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(return_value=(report, False))),
            patch("app.routers.country.archive_service.save_report", new=AsyncMock()),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertIsNone(payload["score"]["total"])
        self.assertIsNone(payload["fear_greed"]["value"])
        self.assertIsNone(payload["forecast"]["fair_value"])
        self.assertIsNone(payload["market_data"]["KOSPI"]["change_pct"])

    async def test_get_country_report_uses_public_timeout_budget(self):
        report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "summary",
            "macro_claims": [],
            "key_news": [],
            "institutional_analysis": {"policy_institutions": [], "sell_side": [], "policy_sellside_aligned": False, "consensus_count": 0, "consensus_summary": ""},
            "top_stocks": [],
            "fear_greed": {"value": 50.0, "label": "neutral", "summary": ""},
            "forecast": {"index_ticker": "KS11", "index_name": "KOSPI", "current_price": 1.0, "fair_value": 1.0, "scenarios": [], "confidence_note": ""},
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.1}},
            "generated_at": "2026-04-04T00:00:00",
        }

        with (
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(return_value=(report, False))) as loader,
            patch("app.routers.country.archive_service.save_report", new=AsyncMock()),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(loader.await_args.kwargs["timeout_seconds"], country.COUNTRY_REPORT_PUBLIC_TIMEOUT_SECONDS)
        self.assertTrue(loader.await_args.kwargs["keep_background"])

    async def test_get_country_report_partial_response_skips_inline_prediction_capture(self):
        report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "partial summary",
            "macro_claims": [],
            "key_news": [],
            "institutional_analysis": {"policy_institutions": [], "sell_side": [], "policy_sellside_aligned": False, "consensus_count": 0, "consensus_summary": ""},
            "top_stocks": [],
            "fear_greed": {"value": 50.0, "label": "neutral", "summary": ""},
            "forecast": {"index_ticker": "KS11", "index_name": "KOSPI", "current_price": 1.0, "fair_value": 1.0, "scenarios": [], "confidence_note": ""},
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.1}},
            "generated_at": "2026-04-04T00:00:00",
            "partial": True,
            "fallback_reason": "country_report_timeout",
            "errors": [],
        }

        with (
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(return_value=None)),
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(return_value=(report, True))),
            patch("app.routers.country.prediction_capture_service.capture_report_predictions", new=AsyncMock(side_effect=AssertionError("inline capture should be skipped"))),
            patch("app.routers.country.archive_service.save_report", new=AsyncMock(side_effect=AssertionError("partial response should not archive inline"))),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertTrue(payload["partial"])

    async def test_get_country_report_skips_slow_cached_lookups(self):
        report = {
            "country": {"code": "KR", "name": "Korea", "name_local": "한국"},
            "market_summary": "summary",
            "macro_claims": [],
            "key_news": [],
            "institutional_analysis": {"policy_institutions": [], "sell_side": [], "policy_sellside_aligned": False, "consensus_count": 0, "consensus_summary": ""},
            "top_stocks": [],
            "fear_greed": {"value": 50.0, "label": "neutral", "summary": ""},
            "forecast": {"index_ticker": "KS11", "index_name": "KOSPI", "current_price": 1.0, "fair_value": 1.0, "scenarios": [], "confidence_note": ""},
            "market_data": {"KOSPI": {"price": 2500.0, "change_pct": 0.1}},
            "generated_at": "2026-04-04T00:00:00",
        }

        async def _slow_cached(*args, **kwargs):
            await asyncio.sleep(0.05)
            return report

        with (
            patch("app.routers.country.COUNTRY_REPORT_CACHE_LOOKUP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.COUNTRY_REPORT_ARCHIVE_LOOKUP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(side_effect=_slow_cached)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(side_effect=_slow_cached)),
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(return_value=(report, False))) as loader,
            patch("app.routers.country.archive_service.save_report", new=AsyncMock()),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        loader.assert_awaited_once()

    async def test_get_country_report_returns_memory_guard_fallback_before_heavy_analysis_under_pressure(self):
        fallback_payload = {
            "country": {"code": "KR"},
            "market_summary": "메모리 보호 모드 fallback",
            "partial": True,
            "fallback_reason": "country_report_memory_guard",
            "errors": [],
        }

        with (
            patch("app.routers.country.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch("app.routers.country.get_memory_pressure_snapshot", return_value={"pressure_ratio": 0.86}),
            patch("app.routers.country._load_latest_cached_country_report", new=AsyncMock(return_value=None)),
            patch(
                "app.routers.country._load_latest_archived_country_report",
                new=AsyncMock(side_effect=AssertionError("archived lookup should be skipped")),
            ) as archived_lookup,
            patch("app.routers.country._build_country_report_fallback", new=AsyncMock(return_value=fallback_payload)) as builder,
            patch("app.routers.country._load_country_report_with_fallback", new=AsyncMock(side_effect=AssertionError("heavy analysis path should be skipped"))),
        ):
            response = await country.get_country_report("KR")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["fallback_reason"], "country_report_memory_guard")
        builder.assert_awaited_once()
        archived_lookup.assert_not_awaited()
        self.assertFalse(builder.await_args.kwargs["include_archived_report"])
        self.assertFalse(builder.await_args.kwargs["include_quick_candidates"])

    async def test_market_opportunities_returns_memory_guard_placeholder_without_live_quick_fetch(self):
        placeholder_payload = {
            "country_code": "KR",
            "generated_at": "2026-04-11T08:00:00",
            "market_regime": None,
            "universe_size": 0,
            "total_scanned": 0,
            "quote_available_count": 0,
            "detailed_scanned_count": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "universe_source": "fallback",
            "universe_note": "memory guard placeholder",
            "opportunities": [],
        }

        with (
            patch("app.routers.country.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch("app.routers.country.get_memory_pressure_snapshot", return_value={"pressure_ratio": 0.86}),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(return_value=None)),
            patch("app.routers.country.market_service.build_market_opportunities_placeholder", return_value=placeholder_payload),
            patch("app.routers.country.market_service.get_market_opportunities_quick", new=AsyncMock(side_effect=AssertionError("live quick fetch should be skipped"))),
        ):
            response = await country.get_market_opportunities("KR", limit=12)

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "opportunity_memory_guard")
        self.assertEqual(response["fallback_tier"], "placeholder")

    async def test_country_report_fallback_timeboxes_snapshot_and_quick_candidate_lookups_under_pressure(self):
        async def _slow_lookup(*args, **kwargs):
            await asyncio.sleep(0.05)
            return None

        with (
            patch("app.routers.country.COUNTRY_REPORT_FALLBACK_COUNTRIES_LOOKUP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.COUNTRY_REPORT_ARCHIVE_LOOKUP_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.COUNTRY_REPORT_FALLBACK_CACHED_OPPORTUNITY_TIMEOUT_SECONDS", 0.01),
            patch("app.routers.country.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch("app.routers.country.get_memory_pressure_snapshot", return_value={"pressure_ratio": 0.86}),
            patch("app.data.cache.get", new=AsyncMock(side_effect=_slow_lookup)),
            patch("app.routers.country._load_latest_archived_country_report", new=AsyncMock(side_effect=_slow_lookup)),
            patch("app.routers.country.market_service.get_cached_market_opportunities", new=AsyncMock(side_effect=_slow_lookup)),
            patch("app.routers.country.market_service.get_cached_market_opportunities_quick", new=AsyncMock(side_effect=_slow_lookup)),
            patch(
                "app.routers.country.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=AssertionError("high-pressure fallback should skip live quick candidates")),
            ),
        ):
            response = await country._build_country_report_fallback(
                "KR",
                reason="country_report_timeout",
                error_code="SP-5018",
                detail="실시간 계산이 지연되고 있습니다.",
            )

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "country_report_timeout")
        self.assertEqual(response["top_stocks"], [])

    async def test_country_report_memory_guard_fallback_skips_archived_and_quick_candidate_lookups(self):
        with (
            patch("app.data.cache.get", new=AsyncMock(return_value=None)),
            patch(
                "app.routers.country._load_latest_archived_country_report",
                new=AsyncMock(side_effect=AssertionError("archived lookup should be skipped")),
            ),
            patch(
                "app.routers.country.market_service.get_cached_market_opportunities",
                new=AsyncMock(side_effect=AssertionError("cached opportunities should be skipped")),
            ),
            patch(
                "app.routers.country.market_service.get_cached_market_opportunities_quick",
                new=AsyncMock(side_effect=AssertionError("cached quick opportunities should be skipped")),
            ),
            patch(
                "app.routers.country.market_service.get_market_opportunities_quick",
                new=AsyncMock(side_effect=AssertionError("live quick opportunities should be skipped")),
            ),
        ):
            response = await country._build_country_report_fallback(
                "KR",
                reason="country_report_memory_guard",
                error_code=None,
                detail="메모리 보호 응답입니다.",
                include_archived_report=False,
                include_quick_candidates=False,
            )

        self.assertTrue(response["partial"])
        self.assertEqual(response["fallback_reason"], "country_report_memory_guard")
        self.assertEqual(response["top_stocks"], [])

    async def test_load_country_report_with_fallback_returns_without_waiting_for_cancellation_cleanup(self):
        started = asyncio.Event()

        async def _slow_analyze(*args, **kwargs):
            started.set()
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                await asyncio.sleep(0.2)
                raise

        fallback_payload = {
            "country": {"code": "KR"},
            "market_summary": "fallback",
            "partial": True,
            "fallback_reason": "country_report_timeout",
            "errors": ["SP-5018"],
        }

        with (
            patch("app.routers.country.analyze_country", new=AsyncMock(side_effect=_slow_analyze)),
            patch("app.routers.country._build_country_report_fallback", new=AsyncMock(return_value=fallback_payload)),
        ):
            started_at = time.perf_counter()
            response, partial = await country._load_country_report_with_fallback(
                "KR",
                timeout_seconds=0.01,
                keep_background=False,
            )
            elapsed = time.perf_counter() - started_at

        self.assertTrue(partial)
        self.assertEqual(response["fallback_reason"], "country_report_timeout")
        self.assertLess(elapsed, 0.08)


if __name__ == "__main__":
    unittest.main()
