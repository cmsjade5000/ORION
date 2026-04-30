from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_harness():
    repo_root = Path(__file__).resolve().parents[1]
    script_dir = repo_root / "scripts"
    sys.path.insert(0, str(script_dir))
    script_path = script_dir / "orion_realistic_prompt_queue_harness.py"
    spec = importlib.util.spec_from_file_location("orion_realistic_prompt_queue_harness", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOrionRealisticPromptQueueHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = _load_harness()
        cls.fixture_path = Path(__file__).resolve().parent / "fixtures" / "orion_realistic_user_prompts.jsonl"

    def test_fixture_file_is_jsonl_with_required_queue_metadata(self):
        fixtures = self.harness.load_fixtures(self.fixture_path)
        self.assertGreaterEqual(len(fixtures), 10)
        ids = [item["id"] for item in fixtures]
        self.assertEqual(len(ids), len(set(ids)))
        for item in fixtures:
            with self.subTest(item=item["id"]):
                self.harness.validate_fixture(item)
                self.assertIn("prompt", item)
                self.assertIn("expected_behavior", item)
                self.assertIn("queue_behavior", item)
                self.assertIn("safety_constraints", item)
                self.assertEqual(item["queue_behavior"]["owner"], "ORION")

    def test_harness_runs_realistic_prompts_through_runner_and_job_summary(self):
        fixtures = self.harness.load_fixtures(self.fixture_path)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = self.harness.run_fixture_set(fixtures, keep_root=root)

            self.assertTrue(report["ok"])
            self.assertEqual(len(report["results"]), len(fixtures))
            summary = json.loads((root / "tasks" / "JOBS" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["job_count"], len(fixtures))
            self.assertEqual(summary["counts"]["complete"], len(fixtures) - 1)
            self.assertEqual(summary["counts"]["cancelled"], 1)
            self.assertEqual(summary["result_counts"]["ok"], len(fixtures) - 1)
            self.assertEqual(summary["result_counts"]["cancelled"], 1)

            by_id = {result["id"]: result for result in report["results"]}
            self.assertTrue(by_id["retry-last-failed-no-duplicate"]["retrying_observed"])

            inbox_text = (root / "tasks" / "INBOX" / "ORION.md").read_text(encoding="utf-8")
            self.assertIn("Original Prompt: ORION, help me plan the next three steps", inbox_text)
            self.assertEqual(inbox_text.count("Idempotency Key: realistic-prompt:duplicate-send-twice"), 1)

            for result in report["results"]:
                with self.subTest(result=result["id"]):
                    expected_state = "cancelled" if result["id"] == "cancel-queued-task" else "complete"
                    expected_status = "cancelled" if result["id"] == "cancel-queued-task" else "ok"
                    self.assertEqual(result["state"], expected_state)
                    self.assertEqual(result["result_status"], expected_status)
                    self.assertTrue(result["job_id"])
                    self.assertTrue(result["workflow_id"])
                    self.assertTrue(result["queued_digest"])
                    self.assertTrue(result["result_digest"])


if __name__ == "__main__":
    unittest.main()
