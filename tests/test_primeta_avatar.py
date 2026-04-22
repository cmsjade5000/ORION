import importlib.util
import json
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


class TestPrimetaAvatar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        script_path = cls.repo / "scripts" / "primeta_avatar.py"
        spec = importlib.util.spec_from_file_location("primeta_avatar", script_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)
        cls.config = json.loads((cls.repo / "config" / "mcporter.json").read_text(encoding="utf-8"))
        cls.readme = (cls.repo / "README.md").read_text(encoding="utf-8")
        cls.doc = (cls.repo / "docs" / "PRIMETA_AVATAR_LAYER.md").read_text(encoding="utf-8")

    def test_mcporter_config_registers_primeta_server(self):
        primeta = self.config["mcpServers"]["primeta"]
        self.assertEqual(primeta["url"], "https://primeta.ai/mcp")
        self.assertIn("avatar presentation layer", primeta["description"])

    def test_docs_keep_primeta_optional(self):
        self.assertIn("optional avatar/presentation layer", self.readme)
        self.assertIn("presentation-only", self.doc)
        self.assertIn("does not replace ORION's routing", self.readme)

    def test_status_command_uses_named_server_and_json_output(self):
        with mock.patch.object(
            self.module,
            "_run",
            return_value=self.module.CommandResult(
                argv=[],
                returncode=0,
                stdout='{"persona":{"name":"ORION"},"conversation_url":"https://primeta.ai/c/123"}',
                stderr="",
            ),
        ) as run_mock, mock.patch.object(
            sys,
            "argv",
            ["primeta_avatar.py", "--json", "status"],
        ), mock.patch("sys.stdout", new_callable=io.StringIO):
            rc = self.module.main()
        self.assertEqual(rc, 0)
        argv = run_mock.call_args[0][0]
        self.assertEqual(argv[:4], ["mcporter", "--config", str(self.repo / "config" / "mcporter.json"), "call"])
        self.assertIn("primeta.primeta_get_status", argv)
        self.assertIn("--output", argv)
        self.assertIn("json", argv)

    def test_send_command_builds_expected_payload(self):
        with mock.patch.object(
            self.module,
            "_run",
            return_value=self.module.CommandResult(argv=[], returncode=0, stdout="{}", stderr=""),
        ) as run_mock:
            result = self.module._call(
                self.repo / "config" / "mcporter.json",
                "primeta",
                "primeta_send",
                {"text": "[friendly] done"},
            )
        self.assertIsInstance(result, self.module.CommandResult)
        argv = run_mock.call_args[0][0]
        self.assertIn("primeta.primeta_send", argv)
        self.assertIn("--args", argv)
        self.assertIn(json.dumps({"text": "[friendly] done"}), argv)


if __name__ == "__main__":
    unittest.main()
