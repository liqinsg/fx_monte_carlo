import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "mc_daily.yml"


class McDailyWorkflowRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_passes_daily_timeframe(self):
        self.assertIn("run: python fx_monte_carlo.py D", self.workflow_text)

    def test_workflow_stages_existing_generated_directories(self):
        self.assertIn("git add mc_daily_results/ api/", self.workflow_text)
        self.assertNotIn("git add daily_results/ weekly_results/ api/", self.workflow_text)


if __name__ == "__main__":
    unittest.main()
