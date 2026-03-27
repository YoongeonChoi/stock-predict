import json
import unittest
from unittest.mock import AsyncMock, patch

from app.scoring.confidence import clear_empirical_calibration_profiles
from app.services import confidence_calibration_service


def _snapshot(raw_support: float, prediction_type: str) -> dict:
    strong = raw_support >= 0.5
    return {
        "prediction_type": prediction_type,
        "horizon_bucket": 1 if prediction_type == "next_day" else 5 if prediction_type.endswith("5d") else 20,
        "raw_support": raw_support,
        "distribution_support": min(1.0, raw_support + 0.05),
        "analog_support": 0.68 if strong else 0.34,
        "analog_available": True,
        "regime_support": 0.58 if strong else 0.41,
        "edge_support": 0.64 if strong else 0.26,
        "agreement_support": 0.73 if strong else 0.31,
        "agreement_available": True,
        "data_quality_support": 0.82,
        "uncertainty_support": 0.79 if strong else 0.49,
        "volatility_support": 0.71 if strong else 0.44,
    }


class ConfidenceCalibrationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        clear_empirical_calibration_profiles()

    async def test_refresh_empirical_profiles_fits_next_day_profile(self):
        next_day_rows = []
        for index in range(30):
            hit = index % 2 == 0
            raw_support = 0.81 if hit else 0.27
            next_day_rows.append(
                {
                    "reference_price": 100.0,
                    "actual_close": 103.0 if hit else 97.0,
                    "direction": "up",
                    "calibration_json": json.dumps(_snapshot(raw_support, "next_day")),
                }
            )

        async def _prediction_rows(prediction_type: str, limit: int = 2000):
            if prediction_type == "next_day":
                return next_day_rows
            return []

        with patch(
            "app.services.confidence_calibration_service.db.prediction_evaluated_samples",
            new=AsyncMock(side_effect=_prediction_rows),
        ):
            profiles = await confidence_calibration_service.refresh_empirical_profiles()

        self.assertIn("next_day", profiles)
        profile = profiles["next_day"]
        self.assertEqual(profile.prediction_type, "next_day")
        self.assertEqual(profile.sample_count, 30)
        self.assertLessEqual(profile.brier_score, profile.prior_brier_score)

        summary = confidence_calibration_service.get_profile_summary()
        self.assertEqual(summary[0]["prediction_type"], "next_day")
        self.assertEqual(summary[0]["sample_count"], 30)

