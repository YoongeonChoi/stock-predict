import unittest

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


if __name__ == "__main__":
    unittest.main()
