import unittest
from unittest.mock import AsyncMock, patch

from app.services import portfolio_service, research_service


class ResearchAndPortfolioTests(unittest.IsolatedAsyncioTestCase):
    async def test_prediction_lab_normalizes_breakdowns(self):
        with (
            patch("app.services.research_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.research_service.cache.set", new=AsyncMock()),
            patch("app.services.research_service.archive_service.refresh_prediction_accuracy", new=AsyncMock()),
            patch(
                "app.services.research_service.db.prediction_stats",
                new=AsyncMock(
                    return_value={
                        "stored_predictions": 12,
                        "pending_predictions": 2,
                        "total_predictions": 10,
                        "within_range": 7,
                        "within_range_rate": 0.7,
                        "direction_hits": 6,
                        "direction_accuracy": 0.6,
                        "avg_error_pct": 1.8,
                        "avg_confidence": 63.0,
                    }
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_recent",
                new=AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "scope": "stock",
                            "symbol": "AAPL",
                            "country_code": "US",
                            "target_date": "2026-03-20",
                            "reference_date": "2026-03-19",
                            "reference_price": 100.0,
                            "predicted_close": 101.0,
                            "predicted_low": 99.5,
                            "predicted_high": 102.0,
                            "actual_close": 101.5,
                            "direction": "up",
                            "confidence": 67.0,
                            "up_probability": 61.0,
                            "model_version": "signal-v2.1",
                            "created_at": 1.0,
                            "evaluated_at": 2.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_daily_trend",
                new=AsyncMock(
                    return_value=[
                        {
                            "target_date": "2026-03-20",
                            "total": 3,
                            "evaluated_total": 3,
                            "direction_hits": 2,
                            "within_range": 2,
                            "avg_abs_error": 0.013,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_country_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "US",
                            "total": 6,
                            "direction_hits": 4,
                            "within_range": 5,
                            "avg_abs_error": 0.011,
                            "avg_confidence": 62.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_scope_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "stock",
                            "total": 8,
                            "direction_hits": 5,
                            "within_range": 6,
                            "avg_abs_error": 0.012,
                            "avg_confidence": 61.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_model_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "signal-v2.1",
                            "total": 10,
                            "direction_hits": 6,
                            "within_range": 7,
                            "avg_abs_error": 0.018,
                            "avg_confidence": 63.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_confidence_buckets",
                new=AsyncMock(
                    return_value=[
                        {
                            "bucket": "65-74",
                            "total": 5,
                            "avg_confidence": 68.0,
                            "realized_up_rate": 60.0,
                            "direction_accuracy": 64.0,
                            "avg_error_pct": 1.4,
                        }
                    ]
                ),
            ),
        ):
            result = await research_service.get_prediction_lab(limit_recent=20, refresh=True)

        self.assertEqual(result["accuracy"]["total_predictions"], 10)
        self.assertEqual(result["breakdown"]["by_country"][0]["label"], "US")
        self.assertEqual(result["recent_records"][0]["direction_hit"], True)
        self.assertTrue(result["insights"])

    async def test_portfolio_empty_snapshot(self):
        with (
            patch("app.services.portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.portfolio_service.cache.set", new=AsyncMock()),
            patch("app.services.portfolio_service.db.portfolio_list", new=AsyncMock(return_value=[])),
        ):
            result = await portfolio_service.get_portfolio()

        self.assertEqual(result["summary"]["holding_count"], 0)
        self.assertEqual(result["risk"]["overall_label"], "empty")
        self.assertTrue(result["risk"]["playbook"])
