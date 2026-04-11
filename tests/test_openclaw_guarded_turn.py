import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestOpenClawGuardedTurn(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "openclaw_guarded_turn.py"

    def _write_fake_openclaw(self, root: Path, *, response_text: str) -> None:
        scripts_dir = root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        fake = scripts_dir / "openclaww.sh"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [ \"${1:-}\" = \"agent\" ]; then\n"
            "  cat <<'JSON'\n"
            f"{{\"result\":{{\"payloads\":[{{\"text\":{json.dumps(response_text)} }}]}}}}\n"
            "JSON\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"${1:-}\" = \"message\" ] && [ \"${2:-}\" = \"send\" ]; then\n"
            f"  echo \"sent\" >> {str((root / 'tmp' / 'sent.log').as_posix())}\n"
            "  exit 0\n"
            "fi\n"
            "echo \"unsupported\" >&2\n"
            "exit 9\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)

    def _write_rules(self, root: Path, *, block_mode: str) -> None:
        cfg = root / "config"
        cfg.mkdir(parents=True, exist_ok=True)
        rules = {
            "version": 1,
            "name": "test_rules",
            "default_mode": "audit",
            "rules": [
                {
                    "id": "R6_ANNOUNCE_SKIP",
                    "description": "announce prompt exact response",
                    "severity": "critical",
                    "mode": block_mode,
                    "validator": "announce_skip_exact",
                    "applies_to": ["orion_reply"],
                    "trigger_tags_any": ["announce_prompt"],
                    "exact_response": "ANNOUNCE_SKIP",
                    "remediation": "use ANNOUNCE_SKIP"
                }
            ]
        }
        (cfg / "orion_policy_rules.json").write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")

    def test_block_mode_suppresses_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tmp").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root, response_text="Not the expected response")
            self._write_rules(root, block_mode="block")

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--runtime-channel",
                    "local",
                    "--message",
                    "A subagent task \"x\" just completed successfully.",
                    "--policy-mode",
                    "block",
                    "--rules",
                    "config/orion_policy_rules.json",
                    "--deliver-channel",
                    "telegram",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("BLOCKED", proc.stderr)
            self.assertFalse((root / "tmp" / "sent.log").exists())

            reports = list((root / "eval" / "history").glob("policy-gate-turn-*.json"))
            self.assertTrue(reports)
            latest = json.loads(reports[-1].read_text(encoding="utf-8"))
            self.assertTrue((latest.get("summary") or {}).get("blocked"))

    def test_pass_allows_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tmp").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root, response_text="ANNOUNCE_SKIP")
            self._write_rules(root, block_mode="block")

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--runtime-channel",
                    "local",
                    "--message",
                    "A subagent task \"x\" just completed successfully.",
                    "--policy-mode",
                    "block",
                    "--rules",
                    "config/orion_policy_rules.json",
                    "--deliver-channel",
                    "telegram",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((root / "tmp" / "sent.log").exists())
            self.assertIn("DELIVERED", proc.stderr)

    def test_sanitizes_internal_tool_wrapper_before_print_and_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tmp").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(
                root,
                response_text='OLCALL>[{"name":"sessions_spawn","arguments":{"agentId":"polaris"}}]ALL>',
            )
            self._write_rules(root, block_mode="block")

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--runtime-channel",
                    "local",
                    "--message",
                    "Spin up POLARIS.",
                    "--policy-mode",
                    "block",
                    "--rules",
                    "config/orion_policy_rules.json",
                    "--deliver-channel",
                    "telegram",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn("OLCALL>", proc.stdout)
            self.assertIn("Internal runtime output was suppressed.", proc.stdout)

    def test_intercepts_dreaming_status_without_model_turn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tmp").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root, response_text="model path should not run")
            self._write_rules(root, block_mode="block")

            proc = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--runtime-channel",
                    "local",
                    "--message",
                    "/dreaming status",
                    "--policy-mode",
                    "block",
                    "--rules",
                    "config/orion_policy_rules.json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("ORION dreaming status", proc.stdout)
            self.assertIn("Memory slot:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
