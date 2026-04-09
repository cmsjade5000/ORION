import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


def _load_module(repo: Path, rel: str, name: str):
    path = repo / rel
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestOrionToolPilotScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.clawhub = _load_module(cls.repo, "scripts/clawhub_skill_refresh.py", "clawhub_skill_refresh")
        cls.firecrawl = _load_module(cls.repo, "scripts/firecrawl_wire_pilot.py", "firecrawl_wire_pilot")
        cls.acpx = _load_module(cls.repo, "scripts/acpx_pilot_check.py", "acpx_pilot_check")
        cls.acpx_smoke = _load_module(cls.repo, "scripts/acpx_runtime_smoke.py", "acpx_runtime_smoke")
        cls.github = _load_module(
            cls.repo, "scripts/github_structured_workflow_pilot.py", "github_structured_workflow_pilot"
        )
        cls.makefile = (cls.repo / "Makefile").read_text(encoding="utf-8")
        cls.scripts_readme = (cls.repo / "scripts" / "README.md").read_text(encoding="utf-8")

    def test_makefile_and_scripts_readme_expose_pilot_targets(self):
        for needle in (
            "firecrawl-wire-pilot:",
            "acpx-pilot:",
            "acpx-smoke:",
            "github-workflow-pilot:",
            "clawhub_skill_refresh.py",
            "firecrawl_wire_pilot.py",
            "acpx_pilot_check.py",
            "acpx_runtime_smoke.py",
            "github_structured_workflow_pilot.py",
        ):
            self.assertTrue(needle in self.makefile or needle in self.scripts_readme)

    def test_clawhub_report_shape(self):
        fake_runs = {
            ("openclaw", "skills", "list"): self.clawhub.CommandResult("list", True, 0, "clawhub\n", ""),
            ("openclaw", "skills", "search", "reminders"): self.clawhub.CommandResult("search reminders", True, 0, "skill-a\nskill-b", ""),
            ("openclaw", "skills", "search", "notes"): self.clawhub.CommandResult("search notes", True, 0, "skill-c", ""),
            ("openclaw", "skills", "search", "github"): self.clawhub.CommandResult("search github", True, 0, "", ""),
            ("openclaw", "skills", "search", "firecrawl"): self.clawhub.CommandResult("search firecrawl", True, 0, "", ""),
        }

        def fake_run(argv, timeout=30):
            key = tuple(argv)
            if key not in fake_runs:
                raise AssertionError(f"unexpected command: {argv}")
            return fake_runs[key]

        with mock.patch.object(self.clawhub, "_run", side_effect=fake_run):
            report = self.clawhub.build_report()
        self.assertIn("tracked_skills", report)
        self.assertIn("search_rows", report)
        self.assertIn("recommended_actions", report)

    def test_firecrawl_report_shape(self):
        plugins_json = '{"plugins":[{"id":"firecrawl","status":"disabled","activationReason":"not in allowlist","origin":"bundled"}]}'
        with mock.patch.object(
            self.firecrawl,
            "_run",
            side_effect=[
                self.firecrawl.CommandResult("plugins", True, 0, plugins_json, ""),
                self.firecrawl.CommandResult("search", True, 0, "firecrawl-search", ""),
            ],
        ):
            report = self.firecrawl.build_report()
        self.assertEqual(report["owner"], "WIRE")
        self.assertIn("plugin_status", report)
        self.assertIn("validation_steps", report)

    def test_acpx_report_shape(self):
        plugins_json = '{"plugins":[{"id":"acpx","status":"disabled","activationReason":"not in allowlist","origin":"bundled"}]}'
        with mock.patch.object(
            self.acpx,
            "_run",
            side_effect=[
                self.acpx.CommandResult("plugins", True, 0, plugins_json, ""),
                self.acpx.CommandResult(
                    "config",
                    True,
                    0,
                    '{"allow":["acpx"],"entries":{"acpx":{"enabled":true,"config":{"cwd":"'
                    + str(self.repo)
                    + '","permissionMode":"approve-reads","nonInteractivePermissions":"fail","pluginToolsMcpBridge":false}}}}',
                    "",
                ),
                self.acpx.CommandResult("mcporter", True, 0, '{"servers":[]}', ""),
            ],
        ):
            report = self.acpx.build_report()
        self.assertEqual(report["owner"], "ATLAS")
        self.assertIn("stop_gates", report)
        self.assertIn("live_policy", report)

    def test_acpx_runtime_smoke_report_shape(self):
        plugins_json = '{"plugins":[{"id":"acpx","status":"loaded","activationReason":"enabled in config","origin":"bundled"}]}'
        config_json = (
            '{"allow":["telegram","acpx"],"entries":{"acpx":{"enabled":true,"config":{"cwd":"'
            + str(self.repo)
            + '","permissionMode":"approve-reads","nonInteractivePermissions":"fail","pluginToolsMcpBridge":false}}}}'
        )
        validate_json = '{"valid":true}'
        with mock.patch.object(
            self.acpx_smoke,
            "_run",
            side_effect=[
                self.acpx_smoke.CommandResult("validate", True, 0, validate_json, ""),
                self.acpx_smoke.CommandResult("config", True, 0, config_json, ""),
                self.acpx_smoke.CommandResult("plugins", True, 0, plugins_json, ""),
            ],
        ):
            report = self.acpx_smoke.build_report()
        self.assertTrue(report["passed"])
        self.assertTrue(report["checks"]["plugin_loaded"])

    def test_github_report_shape(self):
        with mock.patch.object(
            self.github,
            "_run",
            side_effect=[
                self.github.CommandResult("gh version", True, 0, "gh version 2.79.0", ""),
                self.github.CommandResult("gh repo view", True, 0, '{"nameWithOwner":"cmsjade5000/ORION"}', ""),
                self.github.CommandResult("gh auth status", True, 0, "ok", ""),
            ],
        ):
            report = self.github.build_report()
        self.assertEqual(report["owner"], "ORION/ATLAS")
        self.assertTrue(report["auth_ok"])


if __name__ == "__main__":
    unittest.main()
