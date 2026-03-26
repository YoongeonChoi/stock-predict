import unittest
from unittest.mock import AsyncMock, patch

from app.analysis.distributional_return_engine import build_structured_event_context


class DistributionalReturnEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_structured_event_context_falls_back_on_llm_error(self):
        news_items = [
            {
                "title": "삼성전자 실적 개선 기대",
                "description": "메모리 업황 반등 기대감이 커지고 있다.",
                "source": "Naver Search",
                "published": "2026-03-25",
            }
        ]
        filings = [
            {
                "report_name": "주요사항보고서(계약체결)",
                "remark": "대규모 공급계약 체결",
                "source": "OpenDART",
                "receipt_date": "2026-03-25",
            }
        ]

        with patch(
            "app.analysis.distributional_return_engine.ask_json",
            new=AsyncMock(return_value={"error_code": "SP-4005"}),
        ):
            result = await build_structured_event_context(
                ticker="005930.KS",
                asset_name="삼성전자",
                country_code="KR",
                news_items=news_items,
                filings=filings,
                reference_date="2026-03-26",
            )

        self.assertGreater(result.item_count, 0)
        self.assertIn("최근 이벤트", result.summary)

    async def test_build_structured_event_context_uses_structured_items(self):
        news_items = [
            {
                "title": "삼성전자 가이던스 상향",
                "description": "올해 실적 가이던스를 상향 조정했다.",
                "source": "Naver Search",
                "published": "2026-03-25",
            }
        ]
        filings = [
            {
                "report_name": "주요사항보고서(공급계약체결)",
                "remark": "중장기 매출에 긍정적인 계약 체결",
                "source": "OpenDART",
                "receipt_date": "2026-03-24",
            }
        ]
        llm_payload = {
            "items": [
                {
                    "id": "filing_1",
                    "sentiment": 0.8,
                    "surprise": 0.7,
                    "uncertainty": 0.2,
                    "relevance": 0.9,
                    "event_type": "contract",
                    "horizon": "medium",
                },
                {
                    "id": "news_1",
                    "sentiment": 0.4,
                    "surprise": 0.3,
                    "uncertainty": 0.1,
                    "relevance": 0.7,
                    "event_type": "guidance",
                    "horizon": "short",
                },
            ]
        }

        with patch(
            "app.analysis.distributional_return_engine.ask_json",
            new=AsyncMock(return_value=llm_payload),
        ):
            result = await build_structured_event_context(
                ticker="005930.KS",
                asset_name="삼성전자",
                country_code="KR",
                news_items=news_items,
                filings=filings,
                reference_date="2026-03-26",
            )

        self.assertEqual(result.item_count, 2)
        self.assertGreater(result.sentiment, 0.0)
        self.assertIn("GPT 구조화 이벤트", result.summary)
        self.assertIn("contract", result.event_type_scores)


if __name__ == "__main__":
    unittest.main()
