from pathlib import Path
import unittest


class KeepaliveWorkflowTests(unittest.TestCase):
    def test_render_keepalive_workflow_warms_public_backend_routes(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "render-keepalive.yml"
        self.assertTrue(workflow_path.exists())

        workflow = workflow_path.read_text(encoding="utf-8")
        self.assertIn('cron: "*/10 * * * *"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("https://api.yoongeon.xyz/api/health", workflow)
        self.assertIn("https://api.yoongeon.xyz/api/country/KR/report", workflow)

    def test_render_deploy_workflow_triggers_deploy_hook_and_waits_for_version(self):
        workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "render-deploy.yml"
        self.assertTrue(workflow_path.exists())

        workflow = workflow_path.read_text(encoding="utf-8")
        self.assertIn("push:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn("RENDER_DEPLOY_HOOK_URL", workflow)
        self.assertIn("Missing repository secret RENDER_DEPLOY_HOOK_URL", workflow)
        self.assertIn("curl --fail --silent --show-error --request POST", workflow)
        self.assertIn("scripts/wait_for_deployed_version.py", workflow)
        self.assertIn("--expected-version", workflow)


if __name__ == "__main__":
    unittest.main()
