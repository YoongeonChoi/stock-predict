import unittest
from unittest.mock import AsyncMock, patch

from app.services import archive_service


class ArchiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_report_persists_next_day_and_multi_horizon_calibration(self):
        report = {
            "next_day_forecast": {
                "target_date": "2026-03-31",
                "reference_date": "2026-03-28",
                "reference_price": 100.0,
                "predicted_close": 101.2,
                "predicted_low": 98.9,
                "predicted_high": 103.1,
                "up_probability": 61.0,
                "confidence": 68.0,
                "direction": "up",
                "drivers": [{"label": "Momentum"}],
                "calibration_snapshot": {"prediction_type": "next_day", "raw_support": 0.72},
                "model_version": "dist-studentt-v3.2",
            },
            "free_kr_forecast": {
                "reference_date": "2026-03-28",
                "reference_price": 100.0,
                "evidence": [{"label": "Macro"}],
                "model_version": "dist-studentt-v3.2",
                "horizons": [
                    {
                        "horizon_days": 5,
                        "target_date": "2026-04-04",
                        "price_q10": 96.0,
                        "price_q50": 103.0,
                        "price_q90": 109.0,
                        "p_up": 58.0,
                        "p_down": 22.0,
                        "p_flat": 20.0,
                        "confidence": 66.0,
                        "calibration_snapshot": {"prediction_type": "distributional_5d", "raw_support": 0.66},
                    },
                    {
                        "horizon_days": 20,
                        "target_date": "2026-04-25",
                        "price_q10": 94.0,
                        "price_q50": 107.0,
                        "price_q90": 116.0,
                        "p_up": 54.0,
                        "p_down": 24.0,
                        "p_flat": 22.0,
                        "confidence": 63.0,
                        "calibration_snapshot": {"prediction_type": "distributional_20d", "raw_support": 0.61},
                    },
                ],
            },
        }

        with (
            patch("app.services.archive_service.db.archive_save", new=AsyncMock(return_value=42)),
            patch("app.services.archive_service.db.prediction_upsert", new=AsyncMock()) as prediction_upsert,
        ):
            report_id = await archive_service.save_report(
                report_type="stock",
                report=report,
                country_code="KR",
                ticker="005930.KS",
            )

        self.assertEqual(report_id, 42)
        self.assertEqual(prediction_upsert.await_count, 3)
        prediction_types = [item.kwargs["prediction_type"] for item in prediction_upsert.await_args_list]
        self.assertEqual(prediction_types, ["next_day", "distributional_5d", "distributional_20d"])
        self.assertEqual(
            prediction_upsert.await_args_list[1].kwargs["calibration_json"]["prediction_type"],
            "distributional_5d",
        )
        self.assertEqual(
            prediction_upsert.await_args_list[2].kwargs["calibration_json"]["prediction_type"],
            "distributional_20d",
        )
