import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_routing_regression_gate import build_commands, preflight


class TestRunRoutingRegressionGate(unittest.TestCase):
    def test_preflight_requires_openclaw_and_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            baseline = Path(td) / "missing.json"
            with patch("scripts.run_routing_regression_gate.shutil.which", return_value=None):
                errors = preflight(baseline=baseline)
        self.assertIn("missing required command: openclaw", errors)
        self.assertIn(f"missing baseline report: {baseline}", errors)

    def test_build_commands_wires_eval_and_compare_steps(self):
        repo_root = Path("/tmp/orion")
        commands = build_commands(
            repo_root=repo_root,
            baseline=repo_root / "eval/history/baseline-2026-03.json",
            latest_path=repo_root / "eval/latest_report.json",
            compare_json=repo_root / "eval/latest_compare.json",
            compare_md=repo_root / "eval/scorecard.md",
            thinking="low",
            timeout=180,
            tools_prompts_md=repo_root / "docs/routing_sim_tools.md",
        )
        self.assertEqual(len(commands), 2)
        self.assertIn("loop_test_routing_sim.py", commands[0][1])
        self.assertIn("--latest-path", commands[0])
        self.assertIn(str(repo_root / "docs/routing_sim_tools.md"), commands[0])
        self.assertIn("eval_compare.py", commands[1][1])
        self.assertIn(str(repo_root / "eval/history/baseline-2026-03.json"), commands[1])


if __name__ == "__main__":
    unittest.main()
