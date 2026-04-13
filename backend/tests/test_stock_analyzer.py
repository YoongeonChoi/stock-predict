import asyncio
from types import SimpleNamespace
import time
import unittest
from unittest.mock import AsyncMock, patch

from app.analysis import stock_analyzer
from app.analysis.distributional_return_engine import EventFeatures


class StockAnalyzerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stock_summary_timeout_returns_structured_timeout_error(self):
        async def _slow_llm(*args, **kwargs):
            await asyncio.sleep(0.05)
            return {"analysis_summary": "slow"}

        with (
            patch("app.analysis.stock_analyzer.STOCK_ANALYSIS_LLM_TIMEOUT_SECONDS", 0.01),
            patch("app.analysis.stock_analyzer.ask_json", new=AsyncMock(side_effect=_slow_llm)),
        ):
            result = await stock_analyzer._ask_stock_summary_with_timeout("system", "user")

        self.assertEqual(result["error_code"], "SP-4004")

    async def test_event_context_timeout_falls_back_to_heuristic_context(self):
        async def _slow_context(*args, **kwargs):
            await asyncio.sleep(0.05)
            return EventFeatures(summary="slow")

        news_items = [
            {
                "title": "삼성전자 수주 호조",
                "summary": "대규모 공급 계약 체결",
                "source": "naver search",
                "published": "2026-03-27",
            }
        ]

        with (
            patch("app.analysis.stock_analyzer.EVENT_CONTEXT_TIMEOUT_SECONDS", 0.01),
            patch(
                "app.analysis.stock_analyzer.build_structured_event_context",
                new=AsyncMock(side_effect=_slow_context),
            ),
        ):
            result = await stock_analyzer._build_event_context_with_timeout(
                ticker="005930.KS",
                asset_name="삼성전자",
                country_code="KR",
                news_items=news_items,
                filings=[],
                reference_date="2026-03-27",
            )

        self.assertIsInstance(result, EventFeatures)
        self.assertGreaterEqual(result.item_count, 1)
        self.assertNotEqual(result.summary, "slow")

    async def test_public_stock_summary_timeout_returns_empty_fallback_payload(self):
        async def _slow_llm(*args, **kwargs):
            await asyncio.sleep(0.05)
            return {"summary": "slow"}

        with (
            patch("app.analysis.stock_analyzer.STOCK_ANALYSIS_LLM_TIMEOUT_SECONDS", 0.01),
            patch("app.analysis.stock_analyzer.ask_json", new=AsyncMock(side_effect=_slow_llm)),
        ):
            result = await stock_analyzer._ask_public_stock_summary_with_timeout("system", "user")

        self.assertEqual(result, {})

    async def test_quick_stock_cache_write_timebox_returns_without_waiting_for_slow_persist(self):
        async def _slow_cache_write():
            await asyncio.sleep(0.2)

        with patch("app.analysis.stock_analyzer.STOCK_DETAIL_QUICK_CACHE_WRITE_TIMEOUT_SECONDS", 0.01):
            started_at = time.perf_counter()
            result = await stock_analyzer._timebox_quick_stock_cache_write(
                _slow_cache_write(),
                label="stock quick cache write 005930.KS",
            )
            elapsed = time.perf_counter() - started_at

        self.assertFalse(result)
        self.assertLess(elapsed, 0.08)

    async def test_analyze_stock_prefers_latest_cached_detail_before_history_fetch(self):
        cached_snapshot = {
            "ticker": "005930.KS",
            "current_price": 70000,
            "change_pct": 1.2,
            "generated_at": "2026-03-30T08:00:00+00:00",
            "partial": False,
            "fallback_reason": None,
            "errors": [],
        }

        with (
            patch("app.analysis.stock_analyzer.cache.get", new=AsyncMock(return_value=cached_snapshot)),
            patch("app.analysis.stock_analyzer.yfinance_client.get_stock_info", new=AsyncMock(return_value={})),
            patch(
                "app.analysis.stock_analyzer.yfinance_client.get_price_history",
                new=AsyncMock(side_effect=AssertionError("history fetch should not run")),
            ),
        ):
            result = await stock_analyzer.analyze_stock("005930.KS")

        self.assertEqual(result["ticker"], "005930.KS")
        self.assertEqual(result["current_price"], 70000)

    async def test_get_cached_stock_detail_returns_cached_snapshot_when_quote_refresh_fails(self):
        cached_snapshot = {
            "ticker": "005930.KS",
            "current_price": 70100,
            "change_pct": -0.4,
            "generated_at": "2026-03-30T08:00:00+00:00",
            "errors": [],
        }

        async def _timeout_info(*args, **kwargs):
            raise asyncio.TimeoutError

        with (
            patch("app.analysis.stock_analyzer.cache.get", new=AsyncMock(return_value=cached_snapshot)),
            patch("app.analysis.stock_analyzer.yfinance_client.get_stock_info", new=AsyncMock(side_effect=_timeout_info)),
        ):
            result = await stock_analyzer.get_cached_stock_detail("005930.KS", refresh_quote=True)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["current_price"], 70100)
        self.assertEqual(result["change_pct"], -0.4)

    def test_build_public_stock_summary_uses_fallback_without_sell_side_copy(self):
        summary = stock_analyzer._build_public_stock_summary(
            llm_result={
                "summary": "목표가 120000원을 기준으로 매수 구간을 제시합니다.",
                "evidence_for": ["목표가 상향 기대"],
                "evidence_against": [],
                "why_not_buy_now": [],
                "thesis_breakers": [],
                "data_quality": "목표가 기준 데이터",
                "confidence_note": "상향 여력 12%",
            },
            info={"current_price": 72000},
            quant_score=SimpleNamespace(total=74),
            next_day_forecast=SimpleNamespace(
                confidence=61,
                up_probability=54,
                risk_flags=["변동성 확대 시 손절 기준을 다시 확인해야 합니다."],
                drivers=[],
            ),
            market_regime=SimpleNamespace(stance="neutral"),
            trade_plan=SimpleNamespace(
                action="wait_pullback",
                thesis=["이익 체력이 무너지지 않아 관찰 가치는 남아 있습니다."],
                invalidation="주요 지지 구간을 이탈하면 가설을 다시 점검해야 합니다.",
                risk_reward_estimate=0.9,
            ),
            buy_sell_guide=SimpleNamespace(buy_zone_high=68000),
            llm_available=False,
        )

        self.assertNotIn("목표가", summary.summary)
        self.assertNotRegex(summary.summary, r"\d")
        self.assertGreaterEqual(len(summary.evidence_for), 1)
        self.assertGreaterEqual(len(summary.why_not_buy_now), 1)
        self.assertGreaterEqual(len(summary.thesis_breakers), 1)
        self.assertIn("fallback", summary.data_quality.lower())

    def test_build_public_stock_summary_rejects_english_fallback_points(self):
        summary = stock_analyzer._build_public_stock_summary(
            llm_result={},
            info={"current_price": 58800},
            quant_score=SimpleNamespace(total=47),
            next_day_forecast=SimpleNamespace(
                confidence=28,
                up_probability=44.9,
                risk_flags=[
                    "시장 체제가 risk-off 쪽으로 기울어 있어 단기 반등 시도도 변동성이 크게 나올 수 있습니다."
                ],
                drivers=[],
            ),
            market_regime=SimpleNamespace(stance="neutral"),
            trade_plan=SimpleNamespace(
                action="reduce_risk",
                thesis=[
                    "Market regime is rangebound rotation, which creates a mixed tape for this setup."
                ],
                invalidation="수익성이 개선되지 않을 경우",
                risk_reward_estimate=0.8,
            ),
            buy_sell_guide=SimpleNamespace(buy_zone_high=45266.88),
            llm_available=False,
        )

        self.assertTrue(all("Market regime" not in item for item in summary.evidence_for))
        self.assertTrue(all(any("\uac00" <= ch <= "\ud7a3" for ch in item) for item in summary.evidence_for))


if __name__ == "__main__":
    unittest.main()
