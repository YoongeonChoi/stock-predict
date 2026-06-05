import unittest

from app.services.recommendation_policy import (
    POLICY_VERSION,
    PROFILE_PRESETS,
    build_recommendation_policy,
    profile_code_to_optimization_style,
    recommendation_policy_public_view,
)


class RecommendationPolicyTests(unittest.TestCase):
    def test_profile_presets_keep_expected_codes_and_style_mapping(self):
        self.assertEqual(
            list(PROFILE_PRESETS.keys()),
            ["capital_preservation", "conservative", "balanced", "growth", "aggressive"],
        )
        self.assertEqual(profile_code_to_optimization_style("capital_preservation"), "defensive")
        self.assertEqual(profile_code_to_optimization_style("conservative"), "defensive")
        self.assertEqual(profile_code_to_optimization_style("balanced"), "balanced")
        self.assertEqual(profile_code_to_optimization_style("growth"), "offensive")
        self.assertEqual(profile_code_to_optimization_style("aggressive"), "offensive")

    def test_dynamic_policy_adjusts_cash_and_caps_without_changing_profile(self):
        policy = build_recommendation_policy(
            {"profile_code": "aggressive", "persisted": True},
            portfolio_risk={
                "overall_label": "elevated",
                "portfolio_up_probability": 46.0,
                "risk_off_weight": 38.0,
            },
            market_view=[{"country_code": "KR", "stance": "risk_off"}],
        )

        self.assertEqual(policy["profile_code"], "aggressive")
        self.assertEqual(policy["style"], "offensive")
        self.assertGreater(policy["cash_buffer_pct"], PROFILE_PRESETS["aggressive"]["cash_buffer_pct"])
        self.assertLess(policy["max_single_weight_pct"], PROFILE_PRESETS["aggressive"]["max_single_weight_pct"])
        self.assertGreaterEqual(policy["cash_buffer_pct"], 3.0)
        self.assertLessEqual(policy["cash_buffer_pct"], 60.0)
        self.assertGreaterEqual(len(policy["dynamic_adjustments"]), 2)

    def test_public_view_exposes_resolved_params_and_policy_version(self):
        policy = build_recommendation_policy({"profile_code": "balanced", "persisted": False})
        public = recommendation_policy_public_view(policy)

        self.assertEqual(public["policy_version"], POLICY_VERSION)
        self.assertEqual(public["profile_code"], "balanced")
        self.assertFalse(public["profile_persisted"])
        self.assertIn("risk_aversion", public["resolved_params"])
        self.assertIn("probability_edge_weight", public["resolved_params"])


if __name__ == "__main__":
    unittest.main()
