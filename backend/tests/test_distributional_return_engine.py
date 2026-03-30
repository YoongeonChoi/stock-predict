import unittest
from unittest.mock import AsyncMock, patch

from app.analysis.distributional_return_engine import (
    EventFeatures,
    build_distributional_forecast,
    build_structured_event_context,
)
from app.analysis.learned_fusion import LearnedFusionProfile


class DistributionalReturnEngineTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _price_history(start: float = 100.0, step: float = 0.8, days: int = 90) -> list[dict]:
        rows = []
        for index in range(days):
            close = start + step * index + ((index % 5) - 2) * 0.15
            rows.append(
                {
                    "date": f"2026-01-{(index % 28) + 1:02d}",
                    "open": close - 0.8,
                    "high": close + 1.2,
                    "low": close - 1.4,
                    "close": close,
                    "volume": 1_000_000 + index * 1500,
                }
            )
        return rows

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

    async def test_build_structured_event_context_handles_mixed_timezone_dates(self):
        news_items = [
            {
                "title": "삼성전자 공급 계약 기대",
                "description": "수주 기대가 이어지고 있습니다.",
                "source": "Naver Search",
                "published": "2026-03-25T09:30:00+09:00",
            }
        ]
        filings = [
            {
                "report_name": "주요사항보고서(공급계약체결)",
                "remark": "중장기 매출에 긍정적인 계약 체결",
                "source": "OpenDART",
                "receipt_date": "20260324",
            }
        ]
        llm_payload = {
            "items": [
                {
                    "id": "filing_1",
                    "sentiment": 0.7,
                    "surprise": 0.5,
                    "uncertainty": 0.2,
                    "relevance": 0.8,
                    "event_type": "contract",
                    "horizon": "medium",
                },
                {
                    "id": "news_1",
                    "sentiment": 0.4,
                    "surprise": 0.2,
                    "uncertainty": 0.2,
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

    async def test_distributional_forecast_marks_prior_only_when_no_profile_is_available(self):
        with patch(
            "app.analysis.distributional_return_engine.learned_fusion_profile_service.get_profile_for_horizon",
            return_value=None,
        ):
            result = build_distributional_forecast(
                price_history=self._price_history(),
                benchmark_history=self._price_history(start=98.0, step=0.45),
                event_context=EventFeatures(
                    sentiment=0.22,
                    surprise=0.16,
                    uncertainty=0.12,
                    relevance=0.75,
                    item_count=2,
                    summary="테스트 이벤트",
                ),
                analyst_context={},
                fundamental_context={"sector": "Technology", "industry": "Hardware"},
                horizons=(1,),
            )

        self.assertIsNotNone(result)
        assert result is not None
        horizon = result.horizons[1]
        self.assertEqual(horizon.fusion_method, "prior_only")
        self.assertEqual(horizon.fusion_profile_sample_count, 0)
        self.assertIsNotNone(horizon.calibration_snapshot)
        self.assertIn("fusion_features", horizon.calibration_snapshot)
        self.assertIn("graph_context", horizon.calibration_snapshot)
        self.assertIn("fusion_metadata", horizon.calibration_snapshot)

    async def test_distributional_forecast_includes_graph_metadata_when_profile_is_available(self):
        profile = LearnedFusionProfile(
            prediction_type="next_day",
            horizon_days=1,
            intercept=0.0,
            feature_weights={
                "prior_fused_score": 1.1,
                "fundamental_score": 0.25,
                "macro_score": 0.15,
                "event_sentiment": 0.12,
                "event_surprise": 0.08,
                "event_uncertainty": -0.12,
                "flow_score": 0.09,
                "coverage_naver": 0.04,
                "coverage_opendart": 0.05,
                "regime_spread": 0.18,
            },
            sample_count=72,
            positive_rate=0.57,
            brier_score=0.1821,
            prior_brier_score=0.1943,
            fitted_at="2026-03-29T09:30:00",
        )

        with patch(
            "app.analysis.distributional_return_engine.learned_fusion_profile_service.get_profile_for_horizon",
            return_value=profile,
        ):
            result = build_distributional_forecast(
                price_history=self._price_history(start=112.0, step=0.9),
                benchmark_history=self._price_history(start=109.0, step=0.4),
                event_context=EventFeatures(
                    sentiment=0.34,
                    surprise=0.21,
                    uncertainty=0.14,
                    relevance=0.8,
                    item_count=3,
                    summary="테스트 이벤트",
                ),
                analyst_context={
                    "graph_context_seed": {
                        "peer_snapshots": [
                            {
                                "return_5d": 0.05,
                                "return_20d": 0.16,
                                "return_series": [0.0012 + 0.0001 * (index % 3) for index in range(70)],
                            },
                            {
                                "return_5d": 0.03,
                                "return_20d": 0.11,
                                "return_series": [0.001 + 0.00008 * (index % 4) for index in range(70)],
                            },
                        ],
                        "news_relation_support": 0.55,
                    }
                },
                fundamental_context={"sector": "Technology", "industry": "Hardware"},
                horizons=(1,),
            )

        self.assertIsNotNone(result)
        assert result is not None
        horizon = result.horizons[1]
        self.assertEqual(horizon.fusion_method, "learned_blended_graph")
        self.assertTrue(horizon.graph_context_used)
        self.assertGreater(horizon.graph_coverage or 0.0, 0.0)
        self.assertGreater(horizon.fusion_blend_weight or 0.0, 0.0)
        self.assertEqual(horizon.fusion_profile_sample_count, 72)
        self.assertEqual(horizon.fusion_profile_fitted_at, "2026-03-29T09:30:00")


if __name__ == "__main__":
    unittest.main()
