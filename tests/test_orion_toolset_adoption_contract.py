import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


class TestOrionToolsetAdoptionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.agents = (cls.repo / "AGENTS.md").read_text(encoding="utf-8")
        cls.readme = (cls.repo / "README.md").read_text(encoding="utf-8")
        cls.makefile = (cls.repo / "Makefile").read_text(encoding="utf-8")
        cls.scripts_readme = (cls.repo / "scripts" / "README.md").read_text(encoding="utf-8")
        cls.upgrade_notes = (cls.repo / "docs" / "OPENCLAW_2026_3_13_UPGRADE_NOTES.md").read_text(
            encoding="utf-8"
        )
        cls.baseline_doc = (
            cls.repo / "docs" / "ORION_RUNTIME_BASELINE_2026_04_07.md"
        ).read_text(encoding="utf-8")
        cls.pilots_doc = (cls.repo / "docs" / "ORION_TOOL_PILOTS_2026_04.md").read_text(
            encoding="utf-8"
        )
        cls.sweep_doc = (
            cls.repo / "docs" / "ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md"
        ).read_text(encoding="utf-8")
        cls.historical_adoption_doc = (
            cls.repo / "docs" / "ORION_TOOLSET_ADOPTION_2026_03_22.md"
        ).read_text(encoding="utf-8")

    def test_agents_adds_openai_docs_mcp_guidance(self):
        self.assertIn("OpenAI Docs Retrieval", self.agents)
        self.assertIn("official OpenAI Docs MCP path", self.agents)

    def test_readme_and_scripts_readme_reference_toolset_artifacts(self):
        self.assertIn("docs/ORION_RUNTIME_BASELINE_2026_04_07.md", self.readme)
        self.assertIn("docs/ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md", self.readme)
        self.assertIn("orion_toolset_audit.py", self.scripts_readme)
        self.assertIn("make toolset-audit", self.scripts_readme)

    def test_makefile_exposes_toolset_audit_target(self):
        self.assertIn("toolset-audit:", self.makefile)
        self.assertIn("scripts/orion_toolset_audit.py", self.makefile)

    def test_baseline_docs_capture_template_vs_runtime_split(self):
        self.assertIn("Live OpenClaw runtime is `2026.4.5`", self.baseline_doc)
        self.assertIn("memory-core", self.baseline_doc)
        self.assertIn("ClawHub-backed skill discovery is available now", self.baseline_doc)
        self.assertIn("checked-in template", self.baseline_doc)
        self.assertIn("Historical note", self.historical_adoption_doc)

    def test_current_docs_cover_pilots_and_sweep_outputs(self):
        for needle in (
            "ClawHub Review Workflow",
            "Firecrawl",
            "ACPX Specialist Pilot",
            "Structured GitHub Workflow Expansion",
            "What Changed",
            "What Remains Deferred",
            "Recommended Next Pilots",
        ):
            self.assertTrue(
                needle in self.pilots_doc or needle in self.sweep_doc,
                msg=f"missing needle: {needle}",
            )

    def test_audit_script_exports_report_builder(self):
        script_path = self.repo / "scripts" / "orion_toolset_audit.py"
        spec = importlib.util.spec_from_file_location("orion_toolset_audit", script_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fake_results = {
            ("openclaw", "--version"): module.CommandResult("openclaw --version", True, 0, "OpenClaw 2026.4.5", ""),
            ("openclaw", "config", "validate", "--json"): module.CommandResult(
                "openclaw config validate --json", True, 0, '{"valid": true}', ""
            ),
            ("openclaw", "config", "get", "plugins"): module.CommandResult(
                "openclaw config get plugins",
                True,
                0,
                '{"allow":["telegram","open-prose"],"slots":{"memory":"memory-core"},"entries":{"memory-core":{"config":{"dreaming":{"enabled":true}}}}}',
                "",
            ),
            ("openclaw", "plugins", "list", "--json"): module.CommandResult(
                "openclaw plugins list --json",
                True,
                0,
                '{"plugins":[{"id":"acpx","status":"disabled","activationReason":"not in allowlist"},{"id":"browser","status":"disabled","activationReason":"not in allowlist"},{"id":"firecrawl","status":"disabled","activationReason":"not in allowlist"},{"id":"open-prose","status":"loaded","activationReason":"enabled in config"}]}',
                "",
            ),
            ("openclaw", "skills", "list"): module.CommandResult(
                "openclaw skills list", True, 0, "clawhub\n", ""
            ),
            ("openclaw", "agents", "bindings", "--json"): module.CommandResult(
                "openclaw agents bindings --json", True, 0, "[]", ""
            ),
            ("openclaw", "config", "get", "agents"): module.CommandResult(
                "openclaw config get agents", True, 0, "{}", ""
            ),
            ("codex", "--version"): module.CommandResult("codex --version", True, 0, "codex-cli 0.118.0", ""),
            ("codex", "mcp", "list"): module.CommandResult(
                "codex mcp list", True, 0, "No MCP servers configured yet", ""
            ),
        }

        def fake_run(argv, timeout=30):
            key = tuple(argv)
            if key not in fake_results:
                raise AssertionError(f"unexpected command: {argv}")
            return fake_results[key]

        with mock.patch.object(module, "_run", side_effect=fake_run):
            report = module.build_report()
        self.assertIn("runtime", report)
        self.assertIn("baseline_rows", report)
        self.assertIn("pilot_recommendations", report)
        self.assertIn("template_defaults", report)


if __name__ == "__main__":
    unittest.main()
