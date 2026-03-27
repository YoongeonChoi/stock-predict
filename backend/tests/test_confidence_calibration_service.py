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


def _rich_snapshot(raw_support: float, prediction_type: str) -> dict:
    return {
        "prediction_type": prediction_type,
        "horizon_bucket": 1 if prediction_type == "next_day" else 5 if prediction_type.endswith("5d") else 20,
        "raw_support": raw_support,
        "distribution_support": min(1.0, raw_support + 0.08),
        "analog_support": min(1.0, max(0.05, raw_support * 0.92)),
        "analog_available": True,
        "regime_support": min(1.0, max(0.05, raw_support * 0.85)),
        "edge_support": min(1.0, max(0.05, raw_support * 1.05)),
        "agreement_support": min(1.0, max(0.05, raw_support * 0.9)),
        "agreement_available": True,
        "data_quality_support": 0.83,
        "uncertainty_support": max(0.05, 0.92 - raw_support * 0.25),
        "volatility_support": max(0.05, 0.88 - raw_support * 0.3),
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
        self.assertIn("max_reliability_gap", summary[0])
        self.assertIn("reliability_bins", summary[0])

    async def test_refresh_empirical_profiles_promotes_isotonic_when_samples_are_rich(self):
        rows = []
        clusters = (
            (0.18, [False] * 50),
            (0.38, [False] * 50),
            (0.62, [True] * 50),
            (0.82, [True] * 50),
        )
        for raw_support, outcomes in clusters:
            for hit in outcomes:
                rows.append(
                    {
                        "reference_price": 100.0,
                        "actual_close": 103.0 if hit else 97.0,
                        "direction": "up",
                        "calibration_json": json.dumps(_rich_snapshot(raw_support, "distributional_5d")),
                    }
                )

        async def _prediction_rows(prediction_type: str, limit: int = 2000):
            if prediction_type == "distributional_5d":
                return rows
            return []

        with patch(
            "app.services.confidence_calibration_service.db.prediction_evaluated_samples",
            new=AsyncMock(side_effect=_prediction_rows),
        ):
            profiles = await confidence_calibration_service.refresh_empirical_profiles()

        profile = profiles["distributional_5d"]
        self.assertEqual(profile.method, "empirical_isotonic_5d")
        self.assertTrue(profile.isotonic_thresholds)
        self.assertTrue(profile.isotonic_values)
        self.assertGreaterEqual(len(profile.reliability_bins or []), 2)
        self.assertGreaterEqual(profile.max_reliability_gap or 0.0, 0.0)

