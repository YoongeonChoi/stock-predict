import asyncio
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


if __name__ == "__main__":
    unittest.main()
