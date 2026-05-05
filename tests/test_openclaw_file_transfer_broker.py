import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "openclaw_file_transfer_broker.py"


def load_broker_module():
    spec = importlib.util.spec_from_file_location("openclaw_file_transfer_broker", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestOpenClawFileTransferBroker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker = load_broker_module()
        cls.template = json.loads((REPO / "openclaw.json.example").read_text(encoding="utf-8"))

    def test_template_contains_disabled_file_transfer_policy_without_wildcard(self):
        entry = self.template["plugins"]["entries"]["file-transfer"]
        self.assertFalse(entry["enabled"])
        nodes = entry["config"]["nodes"]
        self.assertIn("Mac Mini", nodes)
        self.assertNotIn("*", nodes)

    def test_template_allows_only_file_transfer_node_commands(self):
        self.assertEqual(
            self.template["gateway"]["nodes"]["allowCommands"],
            ["dir.list", "file.fetch", "dir.fetch", "file.write"],
        )

    def test_template_policy_uses_broker_safety_defaults(self):
        policy = self.template["plugins"]["entries"]["file-transfer"]["config"]["nodes"]["Mac Mini"]
        self.assertEqual(policy["ask"], "always")
        self.assertIs(policy["followSymlinks"], False)
        self.assertEqual(policy["maxBytes"], 16_777_216)

    def test_deny_paths_cover_sensitive_locations(self):
        policy = self.template["plugins"]["entries"]["file-transfer"]["config"]["nodes"]["Mac Mini"]
        deny_paths = set(policy["denyPaths"])
        for required in (
            "/Users/corystoner/.openclaw/secrets/**",
            "/Users/corystoner/.openclaw/.env*",
            "/Users/corystoner/.ssh/**",
            "/Users/corystoner/Library/Keychains/**",
            "/Users/corystoner/Library/**",
            "/Users/corystoner/src/ORION/.git/**",
        ):
            self.assertIn(required, deny_paths)

    def test_write_policy_is_staging_only(self):
        policy = self.template["plugins"]["entries"]["file-transfer"]["config"]["nodes"]["Mac Mini"]
        self.assertEqual(
            policy["allowWritePaths"],
            ["/Users/corystoner/src/ORION/tmp/file-transfer-broker/inbound/**"],
        )

    def test_helper_refuses_missing_node(self):
        with self.assertRaisesRegex(self.broker.BrokerError, "no paired and connected"):
            self.broker.resolve_node([], "Mac Mini")

    def test_helper_refuses_wildcard_policy(self):
        entry = self.broker.plugin_entry("*", enabled=True)
        with self.assertRaisesRegex(self.broker.BrokerError, "wildcard"):
            self.broker.validate_policy(entry)

    def test_render_policy_outputs_valid_json(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "render-policy", "--node-key", "Mac Mini"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["enabled"])
        self.assertIn("Mac Mini", payload["config"]["nodes"])


if __name__ == "__main__":
    unittest.main()
