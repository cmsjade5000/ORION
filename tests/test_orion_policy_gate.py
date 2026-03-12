import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import orion_policy_gate as gate


class TestOrionPolicyGate(unittest.TestCase):
    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[1]

    def _run_main(self, *, payload: dict, rules_path: Path, mode: str) -> int:
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            argv = [
                "orion_policy_gate.py",
                "--input-json",
                str(input_path),
                "--rules",
                str(rules_path),
                "--mode",
                mode,
            ]
            with patch.object(sys, "argv", argv):
                return gate.main()

    def test_audit_mode_returns_zero_with_violation_using_real_config(self):
        rules_path = self._repo_root() / "config" / "orion_policy_rules.json"
        payload = {
            "scope": "orion_reply",
            "request_text": "Can we explore options and execute this now?",
            "response_text": "Proceeding.",
            "metadata": {},
        }

        rule_set = gate.load_rule_set(rules_path)
        report = gate.evaluate_policy(payload=payload, rule_set=rule_set, run_mode="audit")

        self.assertEqual(report["summary"]["violations"], 1)
        self.assertFalse(report["summary"]["blocked"])
        self.assertEqual(self._run_main(payload=payload, rules_path=rules_path, mode="audit"), 0)

    def test_block_mode_returns_two_when_block_effective_violation_exists(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            rules_path = td_path / "rules.json"
            rules_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "name": "test_rules",
                        "default_mode": "audit",
                        "rules": [
                            {
                                "id": "BLOCK_RULE",
                                "description": "Require exact phrase",
                                "severity": "critical",
                                "mode": "block",
                                "validator": "phrase_contract",
                                "applies_to": ["orion_reply"],
                                "required_all": ["ALLOWED_PHRASE"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            payload = {
                "scope": "orion_reply",
                "request_text": "Simple request",
                "response_text": "Different text",
                "metadata": {},
            }

            rc = self._run_main(payload=payload, rules_path=rules_path, mode="block")
            self.assertEqual(rc, 2)

    def test_mixed_intent_exact_phrase_rule_wrong_text_then_passes_exact_phrase(self):
        rules_path = self._repo_root() / "config" / "orion_policy_rules.json"
        rule_set = gate.load_rule_set(rules_path)
        request = "Can we explore options first and execute right now?"

        wrong = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "Do you want to explore or execute now?",
                "metadata": {},
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        wrong_ids = {v["rule_id"] for v in wrong["violations"]}
        self.assertIn("R5_MIXED_INTENT_GATE", wrong_ids)

        exact = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "Do you want to explore or execute right now?",
                "metadata": {},
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        exact_ids = {v["rule_id"] for v in exact["violations"]}
        self.assertNotIn("R5_MIXED_INTENT_GATE", exact_ids)

    def test_announce_prompt_requires_exact_announce_skip(self):
        rules_path = self._repo_root() / "config" / "orion_policy_rules.json"
        rule_set = gate.load_rule_set(rules_path)
        request = 'A subagent task "policy-run" just completed successfully.'

        invalid = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "ANNOUNCE_SKIP with context",
                "metadata": {},
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        invalid_ids = {v["rule_id"] for v in invalid["violations"]}
        self.assertIn("R6_ANNOUNCE_SKIP", invalid_ids)

        valid = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "ANNOUNCE_SKIP",
                "metadata": {},
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        valid_ids = {v["rule_id"] for v in valid["violations"]}
        self.assertNotIn("R6_ANNOUNCE_SKIP", valid_ids)

    def test_completion_proof_flags_claim_without_evidence_and_allows_progress_state(self):
        rules_path = self._repo_root() / "config" / "orion_policy_rules.json"
        rule_set = gate.load_rule_set(rules_path)
        request = "Please configure this service."

        claimed_done = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "I set up the service.",
                "metadata": {
                    "executed_in_turn": False,
                    "has_specialist_result": False,
                },
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        claimed_ids = {v["rule_id"] for v in claimed_done["violations"]}
        self.assertIn("R2_COMPLETION_PROOF", claimed_ids)

        progress_state = gate.evaluate_policy(
            payload={
                "scope": "orion_reply",
                "request_text": request,
                "response_text": "This is queued and pending verification.",
                "metadata": {
                    "executed_in_turn": False,
                    "has_specialist_result": False,
                },
            },
            rule_set=rule_set,
            run_mode="audit",
        )
        progress_ids = {v["rule_id"] for v in progress_state["violations"]}
        self.assertNotIn("R2_COMPLETION_PROOF", progress_ids)


if __name__ == "__main__":
    unittest.main()
