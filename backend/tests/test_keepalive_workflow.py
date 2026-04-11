from pathlib import Path
import unittest


class KeepaliveWorkflowTests(unittest.TestCase):
    def test_render_keepalive_workflow_warms_public_backend_routes(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "render-keepalive.yml"
        self.assertTrue(workflow_path.exists())

        workflow = workflow_path.read_text(encoding="utf-8")
        self.assertIn('cron: "*/10 * * * *"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("https://api.yoongeon.xyz/api/health", workflow)
        self.assertIn("https://api.yoongeon.xyz/api/country/KR/report", workflow)


if __name__ == "__main__":
    unittest.main()
