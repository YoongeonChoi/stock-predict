import asyncio
from types import SimpleNamespace
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


if __name__ == "__main__":
    unittest.main()
