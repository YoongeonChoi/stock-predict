import unittest

from app.analysis.learned_fusion import (
    MIN_FUSION_SAMPLES,
    LearnedFusionProfile,
    apply_learned_fusion,
    build_fusion_feature_map,
    fit_learned_fusion_profile,
    fusion_feature_vector,
)


class LearnedFusionTests(unittest.TestCase):
    def _build_training_rows(self, count: int = 48):
        feature_rows = []
        reference_prices = []
        actual_closes = []
        for index in range(count):
            bullish = index % 2 == 0
            prior_score = 0.85 if bullish else -0.85
            feature_rows.append(
                build_fusion_feature_map(
                    prior_fused_score=prior_score,
                    fundamental_score=0.42 if bullish else -0.38,
                    macro_score=0.18 if bullish else -0.16,
                    event_sentiment=0.55 if bullish else -0.48,
                    event_surprise=0.32 if bullish else -0.24,
                    event_uncertainty=0.18 if bullish else 0.26,
                    flow_score=0.22 if bullish else -0.19,
                    coverage_naver=0.7,
                    coverage_opendart=0.6,
                    regime_spread=0.2 if bullish else -0.2,
                )
            )
            reference_prices.append(100.0)
            actual_closes.append(104.0 if bullish else 96.0)
        return feature_rows, reference_prices, actual_closes

    def test_feature_vector_normalizes_non_finite_values(self):
        vector = fusion_feature_vector(
            {
                "prior_fused_score": float("nan"),
                "fundamental_score": "bad",
                "macro_score": 0.25,
                "event_sentiment": 4.0,
                "event_surprise": -4.0,
                "event_uncertainty": 5.0,
                "flow_score": None,
                "coverage_naver": 4.0,
                "coverage_opendart": -1.0,
                "regime_spread": 4.0,
            }
        )

        self.assertEqual(len(vector), 10)
        self.assertTrue(all(isinstance(value, float) for value in vector))
        self.assertTrue(all(abs(value) <= 2.0 for value in vector[:-3]))
        self.assertGreaterEqual(vector[-3], 0.0)
        self.assertLessEqual(vector[-3], 1.0)
        self.assertGreaterEqual(vector[-2], 0.0)
        self.assertLessEqual(vector[-2], 1.0)
        self.assertGreaterEqual(vector[-1], -1.0)
        self.assertLessEqual(vector[-1], 1.0)

    def test_fit_learned_fusion_profile_returns_none_when_samples_are_insufficient(self):
        feature_rows, reference_prices, actual_closes = self._build_training_rows(count=MIN_FUSION_SAMPLES - 2)

        profile = fit_learned_fusion_profile(
            prediction_type="next_day",
            feature_rows=feature_rows,
            reference_prices=reference_prices,
            actual_closes=actual_closes,
        )

        self.assertIsNone(profile)

    def test_fit_learned_fusion_profile_builds_profile_with_balanced_samples(self):
        feature_rows, reference_prices, actual_closes = self._build_training_rows()

        profile = fit_learned_fusion_profile(
            prediction_type="distributional_5d",
            feature_rows=feature_rows,
            reference_prices=reference_prices,
            actual_closes=actual_closes,
        )

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.horizon_days, 5)
        self.assertGreaterEqual(profile.sample_count, MIN_FUSION_SAMPLES)
        self.assertGreater(profile.prior_brier_score, 0.0)
        self.assertGreater(profile.brier_score, 0.0)
        self.assertTrue(profile.fitted_at)
        self.assertEqual(len(profile.feature_weights), 10)

    def test_apply_learned_fusion_uses_prior_only_without_profile(self):
        feature_map = build_fusion_feature_map(
            prior_fused_score=0.44,
            fundamental_score=0.2,
            macro_score=0.1,
            event_sentiment=0.25,
            event_surprise=0.1,
            event_uncertainty=0.15,
            flow_score=0.05,
            coverage_naver=0.8,
            coverage_opendart=0.4,
            regime_spread=0.1,
        )

        result = apply_learned_fusion(
            horizon_days=1,
            prior_fused_score=0.44,
            feature_map=feature_map,
            profile=None,
            graph_context=None,
            history_bars=140,
            macro_available=True,
            fundamental_available=True,
            flow_available=True,
            event_count=2,
            event_uncertainty=0.15,
        )

        self.assertEqual(result.method, "prior_only")
        self.assertEqual(result.sample_count, 0)
        self.assertEqual(result.blend_weight, 0.0)
        self.assertAlmostEqual(result.fused_score, 0.44, places=6)
        self.assertFalse(result.graph_context_used)

    def test_apply_learned_fusion_uses_graph_method_when_profile_and_context_exist(self):
        feature_rows, reference_prices, actual_closes = self._build_training_rows()
        profile = fit_learned_fusion_profile(
            prediction_type="distributional_20d",
            feature_rows=feature_rows,
            reference_prices=reference_prices,
            actual_closes=actual_closes,
        )
        self.assertIsNotNone(profile)
        assert isinstance(profile, LearnedFusionProfile)

        feature_map = build_fusion_feature_map(
            prior_fused_score=0.62,
            fundamental_score=0.34,
            macro_score=0.2,
            event_sentiment=0.31,
            event_surprise=0.16,
            event_uncertainty=0.12,
            flow_score=0.08,
            coverage_naver=0.9,
            coverage_opendart=0.7,
            regime_spread=0.18,
        )

        result = apply_learned_fusion(
            horizon_days=20,
            prior_fused_score=0.62,
            feature_map=feature_map,
            profile=profile,
            graph_context={
                "used": True,
                "coverage": 0.82,
                "graph_context_score": 0.26,
            },
            history_bars=220,
            macro_available=True,
            fundamental_available=True,
            flow_available=True,
            event_count=3,
            event_uncertainty=0.12,
        )

        self.assertEqual(result.method, "learned_blended_graph")
        self.assertGreater(result.blend_weight, 0.0)
        self.assertTrue(result.graph_context_used)
        self.assertGreater(result.graph_coverage, 0.0)
        self.assertGreater(result.learned_probability, 0.5)


if __name__ == "__main__":
    unittest.main()
