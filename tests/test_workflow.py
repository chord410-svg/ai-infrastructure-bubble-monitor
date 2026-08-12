import unittest
from pathlib import Path


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_schedule_manual_permissions_tests_update_and_pages(self):
        text = Path(".github/workflows/update-and-deploy.yml").read_text(encoding="utf-8")
        for required in (
            "schedule:", "workflow_dispatch:", "contents: write", "pages: write", "id-token: write",
            "python3 -m unittest", "python3 -m src.update", "actions/upload-pages-artifact",
            "actions/deploy-pages", "SEC_USER_AGENT", "concurrency:",
        ):
            self.assertIn(required, text)
        self.assertNotIn("@main", text)
        self.assertNotIn("@v4\n", text)


if __name__ == "__main__":
    unittest.main()
