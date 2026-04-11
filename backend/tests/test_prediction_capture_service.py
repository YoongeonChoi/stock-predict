import unittest
from unittest.mock import AsyncMock, patch

from app.services import prediction_capture_service


class PredictionCaptureServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_market_opportunity_predictions_stores_focus_and_distributional_rows(self):
        payload = {
            "next_day_focus": {
                "ticker": "005930.KS",
                "next_day_forecast": {
                    "target_date": "2026-04-08",
                    "reference_date": "2026-04-07",
                    "reference_price": 85000.0,
                    "predicted_close": 86100.0,
                    "predicted_low": 84200.0,
                    "predicted_high": 87200.0,
                    "up_probability": 62.0,
                    "confidence": 66.0,
                    "direction": "up",
                    "drivers": [{"signal": "momentum", "detail": "반도체 수급"}],
                    "calibration_snapshot": {"prediction_type": "next_day"},
                    "model_version": "dist-studentt-v3.3-lfgraph",
                },
            },
            "opportunities": [
                {
                    "ticker": "000660.KS",
                    "current_price": 182000.0,
                    "target_date_20d": "2026-05-06",
                    "price_q25_20d": 176000.0,
                    "price_q50_20d": 191000.0,
                    "price_q75_20d": 202000.0,
                    "up_probability_20d": 64.0,
                    "down_probability_20d": 18.0,
                    "flat_probability_20d": 18.0,
                    "distribution_confidence_20d": 61.0,
                    "thesis": ["메모리 업황 개선"],
                }
            ],
        }

        with (
            patch("app.services.prediction_capture_service.db.prediction_upsert", new=AsyncMock()) as prediction_upsert,
            patch(
                "app.services.prediction_capture_service.opportunity_radar_lab_service.capture_opportunity_radar_snapshot",
                new=AsyncMock(return_value={"captured_snapshots": 1, "reference_date": "2026-04-07"}),
            ) as capture_snapshot,
        ):
            result = await prediction_capture_service.capture_market_opportunity_predictions(
                "KR",
                payload,
            )

        self.assertEqual(result["captured_predictions"], 2)
        self.assertEqual(result["captured_focus"], 1)
        self.assertEqual(result["captured_opportunities"], 1)
        self.assertEqual(result["captured_snapshots"], 1)
        self.assertEqual(result["radar_snapshot_reference_date"], "2026-04-07")
        self.assertEqual(prediction_upsert.await_count, 2)
        self.assertEqual(prediction_upsert.await_args_list[0].kwargs["prediction_type"], "next_day")
        self.assertEqual(prediction_upsert.await_args_list[1].kwargs["prediction_type"], "distributional_20d")
        capture_snapshot.assert_awaited_once()

    async def test_backfill_recent_archive_predictions_only_writes_missing_rows(self):
        archive_rows = [
            {
                "report_type": "stock",
                "country_code": "KR",
                "ticker": "005930.KS",
                "report_json": {
                    "next_day_forecast": {
                        "target_date": "2026-04-08",
                        "reference_date": "2026-04-07",
                        "reference_price": 85000.0,
                        "predicted_close": 86100.0,
                        "predicted_low": 84200.0,
                        "predicted_high": 87200.0,
                        "up_probability": 62.0,
                        "confidence": 66.0,
                        "direction": "up",
                        "drivers": [{"signal": "momentum", "detail": "반도체 수급"}],
                        "calibration_snapshot": {"prediction_type": "next_day"},
                        "model_version": "dist-studentt-v3.3-lfgraph",
                    }
                },
            }
        ]

        with (
            patch("app.services.prediction_capture_service.db.archive_list", new=AsyncMock(return_value=archive_rows)),
            patch("app.services.prediction_capture_service.db.prediction_record_exists", new=AsyncMock(return_value=False)),
            patch("app.services.prediction_capture_service.db.prediction_upsert", new=AsyncMock()) as prediction_upsert,
        ):
            result = await prediction_capture_service.backfill_recent_archive_predictions(limit=10)

        self.assertEqual(result["checked_reports"], 1)
        self.assertEqual(result["updated_reports"], 1)
        self.assertEqual(result["captured_predictions"], 1)
        prediction_upsert.assert_awaited_once()
