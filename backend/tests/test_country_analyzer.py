import asyncio
import re
import unittest
from unittest.mock import AsyncMock, patch

from app.analysis.country_analyzer import _build_macro_claims, _finalize_public_market_summary, _score_top_stocks
from app.models.country import InstitutionalAnalysis
from app.scoring.country_scorer import build_country_score


class CountryAnalyzerPublicSummaryTests(unittest.TestCase):
    def test_build_macro_claims_prefers_grounded_market_and_macro_data(self):
        claims = _build_macro_claims(
            "KR",
            {
                "base_rate": 2.75,
                "cpi_yoy": 2.1,
                "export_growth": 6.2,
                "industrial_production": 1.4,
            },
            {
                "KOSPI": {"price": 2650.0, "change_pct": 0.84},
                "KOSDAQ": {"price": 812.0, "change_pct": -0.31},
            },
        )

        self.assertEqual([claim.metric for claim in claims], ["KOSPI 등락률", "KOSDAQ 등락률", "기준금리", "소비자물가"])
        self.assertEqual(claims[0].direction, "up")
        self.assertEqual(claims[1].direction, "down")
        self.assertEqual(claims[2].source, "한국은행 ECOS")
        self.assertEqual(claims[3].unit, "%")

    def test_numeric_public_summary_is_downgraded_to_qualitative_summary(self):
        country_score = build_country_score(
            {
                "monetary_policy": {"score": 8.0, "description": "완화적"},
                "economic_growth": {"score": 7.0, "description": "양호"},
                "market_valuation": {"score": 5.0, "description": "중립"},
                "earnings_momentum": {"score": 7.0, "description": "개선"},
                "institutional_consensus": {"score": 7.0, "description": "정렬"},
                "risk_assessment": {"score": 6.0, "description": "관리 가능"},
            }
        )
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[],
            sell_side=[],
            policy_sellside_aligned=True,
            consensus_count=3,
            consensus_summary="정책과 증권사 해석이 비슷합니다.",
        )

        summary = _finalize_public_market_summary(
            raw_summary="한국 시장은 2026년 성장률 2.1%와 수출 6.2% 개선을 반영하고 있습니다.",
            llm_failed=False,
            country_name_local="한국",
            country_score=country_score,
            institutional_analysis=institutional_analysis,
            macro_claims=[],
        )

        self.assertNotRegex(summary, re.compile(r"\d"))
        self.assertIn("한국 시장은", summary)
        self.assertIn("정책 기관과 증권사", summary)

    def test_qualitative_public_summary_is_preserved(self):
        country_score = build_country_score({})
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[],
            sell_side=[],
            policy_sellside_aligned=False,
            consensus_count=0,
            consensus_summary="",
        )

        summary = _finalize_public_market_summary(
            raw_summary="시장은 방향성보다 선별 대응이 중요한 구간입니다.\n\n기관 해석도 업종별로 나뉘어 있습니다.",
            llm_failed=False,
            country_name_local="한국",
            country_score=country_score,
            institutional_analysis=institutional_analysis,
            macro_claims=[],
        )

        self.assertEqual(summary, "시장은 방향성보다 선별 대응이 중요한 구간입니다.\n\n기관 해석도 업종별로 나뉘어 있습니다.")


class CountryAnalyzerResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_score_top_stocks_skips_cancelled_results(self):
        with (
            patch(
                "app.data.universe_data.get_universe",
                new=AsyncMock(return_value={"Information Technology": ["005930.KS", "000660.KS"]}),
            ),
            patch(
                "app.analysis.country_analyzer.gather_limited",
                new=AsyncMock(
                    return_value=[
                        asyncio.CancelledError(),
                        (
                            91.2,
                            "005930.KS",
                            {
                                "name": "Samsung Electronics",
                                "current_price": 71000.0,
                                "prev_close": 70000.0,
                            },
                        ),
                    ]
                ),
            ),
        ):
            top_stocks = await _score_top_stocks("KR", {})

        self.assertEqual(len(top_stocks), 1)
        self.assertEqual(top_stocks[0].ticker, "005930.KS")
        self.assertEqual(top_stocks[0].score, 91.2)


if __name__ == "__main__":
    unittest.main()
