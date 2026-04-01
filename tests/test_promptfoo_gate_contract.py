import unittest
from pathlib import Path


class TestPromptfooGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]

    def _read(self, rel: str) -> str:
        return (self.repo / rel).read_text(encoding="utf-8")

    def test_makefile_points_to_repo_specific_promptfoo_config(self):
        makefile = self._read("Makefile")
        self.assertIn("PROMPTFOO_CONFIG ?= config/promptfoo/orion-safety-gate.yaml", makefile)

    def test_promptfoo_config_exists_and_targets_orion_rules(self):
        cfg = self._read("config/promptfoo/orion-safety-gate.yaml")
        self.assertIn("file://orion-safety-chat.json", cfg)
        self.assertIn("Cron request does not claim completion", cfg)
        self.assertIn("Spending decision asks intake questions", cfg)
        self.assertIn("Crisis language gets safety-first response", cfg)
        self.assertIn("Destructive reset requires confirmation", cfg)
        self.assertIn("prompt-extraction", cfg)
        self.assertIn("pii:direct", cfg)
        self.assertIn("harmful:self-harm", cfg)

    def test_promptfoo_prompt_exists_and_mentions_orion_constraints(self):
        prompt = self._read("config/promptfoo/orion-safety-chat.json")
        self.assertIn("Never claim an operational change is complete unless it was executed and verified in the same turn.", prompt)
        self.assertIn("delegate to ATLAS", prompt)
        self.assertIn("hand off to EMBER", prompt)

    def test_promptfoo_doc_points_to_make_targets_and_outputs(self):
        doc = self._read("docs/PROMPTFOO_GATE.md")
        self.assertIn("make redteam-validate", doc)
        self.assertIn("make redteam-gate", doc)
        self.assertIn(".promptfoo/eval-results.json", doc)
        self.assertIn("config/promptfoo/orion-safety-gate.yaml", doc)


if __name__ == "__main__":
    unittest.main()
