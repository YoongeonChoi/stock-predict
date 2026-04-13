import unittest
from unittest.mock import AsyncMock, patch

from app.services import opportunity_radar_lab_service


class OpportunityRadarLabServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_adjust_opportunity_score_is_bounded_by_runtime_profile(self):
        profile = {
            "status": "active",
            "sample_count": 72,
            "feature_weights": {
                "tag_momentum": 0.12,
                "support_confidence_high": 0.08,
                "support_probability_edge": 0.05,
            },
        }
        with patch.object(opportunity_radar_lab_service, "_runtime_profile", profile):
            result = opportunity_radar_lab_service.adjust_opportunity_score(
                base_score=74.0,
                thesis=["모멘텀 지속", "상대 강도 개선"],
                sector="Information Technology",
                support_snapshot={
                    "confidence_20d": 74.0,
                    "probability_edge_20d": 0.21,
                    "regime_support_20d": 0.62,
                    "analog_support_20d": 0.58,
                    "data_quality_support_20d": 0.77,
                    "risk_reward_estimate": 1.9,
                },
            )

        self.assertTrue(result["applied"])
        self.assertGreater(result["adjusted_score"], 74.0)
        self.assertLessEqual(
            result["adjustment_points"],
            opportunity_radar_lab_service.RADAR_MAX_SCORE_ADJUSTMENT_POINTS,
        )
        self.assertIn("강했습니다", result["reason"])

    async def test_get_lab_summary_aggregates_recent_cohorts(self):
        rows = [
            {
                "id": 1,
                "reference_date": "2026-04-07",
                "evaluated_at": 1712557800.0,
                "symbol": "005930.KS",
                "name": "Samsung Electronics",
                "rank": 1,
                "tags_json": ["모멘텀", "수급"],
                "support_json": {
                    "confidence_20d": 72.0,
                    "regime_support_20d": 0.68,
                },
                "evaluation_json": {
                    "horizons": {
                        "1d": {"direction_hit": True, "actual_return_pct": 1.4},
                        "5d": {"direction_hit": True, "actual_return_pct": 2.8},
                        "20d": {
                            "direction_hit": True,
                            "actual_return_pct": 4.2,
                            "within_band": True,
                            "actual_close": 104.2,
                        },
                    },
                    "review": {
                        "kind": "clean-hit",
                        "summary": "방향과 밴드를 함께 맞췄습니다.",
                        "detail": "모멘텀과 수급이 함께 받쳐 준 사례입니다.",
                    },
                },
            },
            {
                "id": 2,
                "reference_date": "2026-04-07",
                "evaluated_at": None,
                "symbol": "000660.KS",
                "name": "SK hynix",
                "rank": 2,
                "tags_json": ["모멘텀"],
                "support_json": {
                    "confidence_20d": 66.0,
                    "regime_support_20d": 0.51,
                },
                "evaluation_json": {
                    "horizons": {
                        "1d": {"direction_hit": False, "actual_return_pct": -0.8},
                        "5d": {"direction_hit": None, "actual_return_pct": None},
                        "20d": {
                            "direction_hit": None,
                            "actual_return_pct": None,
                            "within_band": None,
                            "actual_close": None,
                        },
                    },
                    "review": {
                        "kind": "miss",
                        "summary": "상승 thesis가 유지되지 못했습니다.",
                        "detail": "추세 follow-through가 나오지 않았습니다.",
                    },
                },
            },
        ]
        profile = {
            "status": "active",
            "sample_count": 28,
            "baseline_success_score": 0.57,
            "updated_at": "2026-04-08T15:30:00",
            "top_positive": [{"key": "tag_momentum", "label": "모멘텀", "delta": 0.05}],
            "top_negative": [{"key": "support_data_quality_weak", "label": "데이터 품질 약함", "delta": -0.03}],
        }

        with (
            patch(
                "app.services.opportunity_radar_lab_service.db.opportunity_radar_snapshot_recent",
                new=AsyncMock(return_value=rows),
            ),
            patch.object(opportunity_radar_lab_service, "_runtime_profile", profile),
        ):
            summary = await opportunity_radar_lab_service.get_lab_summary(limit=20)

        self.assertEqual(summary["stored_snapshots"], 2)
        self.assertEqual(summary["capture_days"], 1)
        self.assertEqual(summary["pending_20d"], 1)
        self.assertEqual(summary["recent_cohorts"][0]["capture_count"], 2)
        self.assertEqual(summary["recent_cohorts"][0]["evaluated_count"], 1)
        self.assertEqual(summary["review_queue"][0]["symbol"], "005930.KS")
        self.assertEqual(summary["tag_breakdown"][0]["label"], "모멘텀")
        self.assertEqual(summary["profile"]["status"], "active")
