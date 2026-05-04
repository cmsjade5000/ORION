import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "canary_stage_harness.py"
    spec = importlib.util.spec_from_file_location("canary_stage_harness", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestCanaryStageHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_module()

    def test_parse_action_spec_accepts_json(self):
        action = self.m._parse_action_spec('{"action":"make","target":"eval-run"}')
        self.assertEqual(action["action"], "make")
        self.assertEqual(action["params"]["target"], "eval-run")

    def test_parse_action_spec_accepts_colon_syntax(self):
        action = self.m._parse_action_spec("make:target=eval-run")
        self.assertEqual(action["action"], "make")
        self.assertEqual(action["params"]["target"], "eval-run")

    def test_parse_action_spec_rejects_unsafe_free_form(self):
        for raw in ("echo hi && whoami", "echo hi | cat", "echo hi; pwd", "echo $(whoami)"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.m._parse_action_spec(raw)

    def test_parse_command_string_rejects_free_form(self):
        for raw in ("python3 -c 'print(\"ok\")'", "make all"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.m._parse_command_string(raw)
        self.assertEqual(self.m._parse_command_string("noop"), [])

    def test_run_command_does_not_use_shell(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            proc = SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
            with mock.patch.object(self.m.subprocess, "run", return_value=proc) as run_mock:
                result = self.m._run_command(["python3", "-V"], cwd, timeout_seconds=15.0)

        self.assertEqual(result["returncode"], 0)
        kwargs = run_mock.call_args.kwargs
        self.assertNotIn("shell", kwargs)


if __name__ == "__main__":
    unittest.main()
