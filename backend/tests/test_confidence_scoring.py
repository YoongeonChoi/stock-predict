import unittest

from app.scoring.confidence import (
    EmpiricalCalibrationProfile,
    analog_support_score,
    calibrate_direction_confidence,
    clear_empirical_calibration_profiles,
    effective_sample_size,
    set_empirical_calibration_profiles,
)
from app.scoring.selection import score_selection_candidate


class ConfidenceScoringTests(unittest.TestCase):
    def tearDown(self):
        clear_empirical_calibration_profiles()

    def test_effective_sample_size_rewards_diversified_weights(self):
        diversified = effective_sample_size([0.25, 0.25, 0.25, 0.25])
        concentrated = effective_sample_size([0.9, 0.1])
        self.assertGreater(diversified, concentrated)

    def test_analog_support_prefers_broad_profitable_analogs(self):
        strong = analog_support_score(
            win_rate_pct=68.0,
            ess=8.5,
            profit_factor=1.9,
            dispersion_pct=2.1,
            reference_volatility_pct=5.0,
        )
        weak = analog_support_score(
            win_rate_pct=52.0,
            ess=1.4,
            profit_factor=1.05,
            dispersion_pct=4.8,
            reference_volatility_pct=5.0,
        )
        self.assertGreater(strong, weak)

    def test_calibrated_confidence_penalizes_long_horizon(self):
        shared_inputs = dict(
            distribution_confidence=78.0,
            regime_probs={"risk_on": 55.0, "neutral": 25.0, "risk_off": 20.0},
            p_up=62.0,
            p_down=18.0,
            median_return_pct=1.2,
            history_bars=252,
            macro_available=True,
            fundamental_available=True,
            flow_available=False,
            event_count=3,
            event_uncertainty=0.2,
            forecast_volatility_pct=7.0,
            realized_volatility_reference_pct=9.0,
            analog_support=None,
            analog_expected_return_pct=None,
        )
        one_day = calibrate_direction_confidence(horizon_days=1, **shared_inputs)
        twenty_day = calibrate_direction_confidence(horizon_days=20, **shared_inputs)
        self.assertGreater(one_day.display_confidence, twenty_day.display_confidence)

    def test_empirical_profile_overrides_bootstrap_calibrator(self):
        set_empirical_calibration_profiles(
            {
                "next_day": EmpiricalCalibrationProfile(
                    prediction_type="next_day",
                    horizon_bucket=1,
                    intercept=-0.4,
                    feature_weights={
                        "raw_support": 3.5,
                        "distribution_support": 0.5,
                        "analog_support": 0.25,
                        "regime_support": 0.1,
                        "edge_support": 0.4,
                        "agreement_support": 0.15,
                        "data_quality_support": 0.1,
                        "uncertainty_support": 0.05,
                        "volatility_support": 0.05,
                        "analog_available": 0.0,
                        "agreement_available": 0.0,
                    },
                    sample_count=48,
                    positive_rate=0.61,
                    brier_score=0.1812,
                    prior_brier_score=0.2144,
                    fitted_at="2026-03-28T09:00:00",
                    method="empirical_sigmoid_1d",
                )
            }
        )

        calibrated = calibrate_direction_confidence(
            horizon_days=1,
            distribution_confidence=76.0,
            regime_probs={"risk_on": 61.0, "neutral": 24.0, "risk_off": 15.0},
            p_up=66.0,
            p_down=14.0,
            median_return_pct=1.8,
            history_bars=252,
            macro_available=True,
            fundamental_available=True,
            flow_available=True,
            event_count=2,
            event_uncertainty=0.12,
            forecast_volatility_pct=6.2,
            realized_volatility_reference_pct=8.4,
            analog_support=0.72,
            analog_expected_return_pct=1.1,
            prediction_type="next_day",
        )

        self.assertEqual(calibrated.calibrator_method, "empirical_sigmoid_1d")
        self.assertIsNotNone(calibrated.calibration_snapshot)
        self.assertEqual(calibrated.calibration_snapshot["prediction_type"], "next_day")
        self.assertGreater(calibrated.display_confidence, 50.0)

    def test_selection_score_respects_confidence_floor(self):
        result = score_selection_candidate(
            expected_excess_return_pct=5.0,
            calibrated_confidence=58.0,
            probability_edge=18.0,
            tail_ratio=1.8,
            regime_alignment=1.0,
            analog_support=0.65,
            data_quality_support=0.7,
            downside_pct=2.0,
            forecast_volatility_pct=8.0,
            action="accumulate",
            execution_bias="press_long",
            legacy_score=82.0,
        )
        self.assertFalse(result.confidence_floor_passed)
        self.assertLess(result.score, 62.0)

    def test_selection_score_rewards_confidence_and_excess_return(self):
        high = score_selection_candidate(
            expected_excess_return_pct=3.2,
            calibrated_confidence=74.0,
            probability_edge=16.0,
            tail_ratio=1.6,
            regime_alignment=1.0,
            analog_support=0.7,
            data_quality_support=0.8,
            downside_pct=3.0,
            forecast_volatility_pct=9.0,
            action="accumulate",
            execution_bias="lean_long",
            legacy_score=76.0,
        )
        low = score_selection_candidate(
            expected_excess_return_pct=1.1,
            calibrated_confidence=54.0,
            probability_edge=6.0,
            tail_ratio=1.1,
            regime_alignment=0.55,
            analog_support=0.35,
            data_quality_support=0.5,
            downside_pct=6.0,
            forecast_volatility_pct=14.0,
            action="wait_pullback",
            execution_bias="stay_selective",
            legacy_score=60.0,
        )
        self.assertGreater(high.score, low.score)
