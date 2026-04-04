import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers import country
from app.runtime import reset_runtime_state


class CountryRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        reset_runtime_state()

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


if __name__ == "__main__":
    unittest.main()
