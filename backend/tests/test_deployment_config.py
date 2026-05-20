import re
import unittest
from pathlib import Path

from app.config import Settings


class DeploymentSettingsTests(unittest.TestCase):
    def test_cors_origins_include_extra_frontend_domains_once(self):
        settings = Settings(
            frontend_url="https://app.yoongeon.xyz/",
            frontend_urls="https://www.yoongeon.xyz, https://stock-predict-preview.vercel.app\nhttps://app.yoongeon.xyz",
        )

        self.assertEqual(
            settings.cors_origins,
            [
                "https://app.yoongeon.xyz",
                "http://localhost:3000",
                "https://www.yoongeon.xyz",
                "https://stock-predict-preview.vercel.app",
            ],
        )

    def test_empty_origin_regex_returns_none(self):
        settings = Settings(frontend_origin_regex="   ")
        self.assertIsNone(settings.cors_origin_regex)

    def test_origin_regex_passthrough(self):
        settings = Settings(frontend_origin_regex=r"^https://.*\.vercel\.app$")
        self.assertEqual(settings.cors_origin_regex, r"^https://.*\.vercel\.app$")

    def test_kosis_stats_id_accepts_legacy_user_stats_id_env_names(self):
        settings = Settings(
            KOSIS_CPI_USER_STATS_ID="legacy-cpi",
            KOSIS_EMPLOYMENT_USER_STATS_ID="legacy-employment",
            KOSIS_INDUSTRIAL_PRODUCTION_USER_STATS_ID="legacy-industrial",
        )
        self.assertEqual(settings.kosis_cpi_stats_id, "legacy-cpi")
        self.assertEqual(settings.kosis_employment_stats_id, "legacy-employment")
        self.assertEqual(settings.kosis_industrial_production_stats_id, "legacy-industrial")

    def test_supabase_server_key_accepts_secret_alias(self):
        settings = Settings(SUPABASE_SECRET_KEY="secret-key")
        self.assertEqual(settings.supabase_server_key, "secret-key")

    def test_safe_mode_disables_startup_prediction_accuracy_refresh(self):
        settings = Settings(
            RENDER=True,
            startup_allow_heavy_render_jobs=False,
            startup_prediction_accuracy_refresh=True,
            startup_prediction_accuracy_refresh_on_render=True,
        )
        self.assertFalse(settings.effective_startup_prediction_accuracy_refresh)

    def test_render_python_version_supports_pinned_data_stack(self):
        root = Path(__file__).resolve().parents[2]
        render_yaml = root / "render.yaml"
        requirements = root / "backend" / "requirements.txt"

        render_config = render_yaml.read_text(encoding="utf-8")
        version_match = re.search(r"key:\s*PYTHON_VERSION\s*\n\s*value:\s*([0-9.]+)", render_config)
        self.assertIsNotNone(version_match)

        python_version = tuple(int(part) for part in version_match.group(1).split(".")[:2])
        requirements_text = requirements.read_text(encoding="utf-8")

        if re.search(r"^numpy==2\.(?:[3-9]|\d{2,})\.", requirements_text, flags=re.MULTILINE):
            self.assertGreaterEqual(python_version, (3, 11))
        if re.search(r"^pandas==(?:3|[4-9]|\d{2,})\.", requirements_text, flags=re.MULTILINE):
            self.assertGreaterEqual(python_version, (3, 11))


if __name__ == "__main__":
    unittest.main()
