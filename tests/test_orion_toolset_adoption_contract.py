import importlib.util
import sys
import unittest
from pathlib import Path


class TestOrionToolsetAdoptionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.agents = (cls.repo / "AGENTS.md").read_text(encoding="utf-8")
        cls.readme = (cls.repo / "README.md").read_text(encoding="utf-8")
        cls.makefile = (cls.repo / "Makefile").read_text(encoding="utf-8")
        cls.scripts_readme = (cls.repo / "scripts" / "README.md").read_text(encoding="utf-8")
        cls.upgrade_notes = (
            cls.repo / "docs" / "OPENCLAW_2026_3_13_UPGRADE_NOTES.md"
        ).read_text(encoding="utf-8")
        cls.adoption_doc = (
            cls.repo / "docs" / "ORION_TOOLSET_ADOPTION_2026_03_22.md"
        ).read_text(encoding="utf-8")

    def test_agents_adds_openai_docs_mcp_guidance(self):
        self.assertIn("OpenAI Docs Retrieval", self.agents)
        self.assertIn("official OpenAI Docs MCP path", self.agents)

    def test_readme_and_scripts_readme_reference_toolset_artifacts(self):
        self.assertIn("docs/ORION_TOOLSET_ADOPTION_2026_03_22.md", self.readme)
        self.assertIn("orion_toolset_audit.py", self.scripts_readme)
        self.assertIn("make toolset-audit", self.scripts_readme)

    def test_makefile_exposes_toolset_audit_target(self):
        self.assertIn("toolset-audit:", self.makefile)
        self.assertIn("scripts/orion_toolset_audit.py", self.makefile)

    def test_repo_docs_describe_tool_warning_as_provider_state_issue(self):
        self.assertIn("active runtime/provider/model/config", self.readme)
        self.assertIn("provider-state gating", self.readme)
        self.assertIn("shipped core tools", self.upgrade_notes)
        self.assertIn("tool profile and active provider/model state are out of sync", self.upgrade_notes)

    def test_adoption_doc_contains_dependency_graph_and_ranked_outputs(self):
        for needle in (
            "## Dependency Graph",
            "`T1` depends_on: `[]`",
            "`T10` depends_on: `[T9]`",
            "Docs MCP + Codex MCP",
            "github-mcp-server",
            "firecrawl",
            "Langfuse",
            "Opik",
            "lossless-claw",
            "voice-call",
            "## T9 Consolidated Shortlist",
            "## T10 Rollout Design",
        ):
            self.assertIn(needle, self.adoption_doc)

    def test_audit_script_exports_report_builder(self):
        script_path = self.repo / "scripts" / "orion_toolset_audit.py"
        spec = importlib.util.spec_from_file_location("orion_toolset_audit", script_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        report = module.build_report()
        self.assertIn("runtime", report)
        self.assertIn("tool_gap_rows", report)
        self.assertIn("adoption_recommendation", report)


if __name__ == "__main__":
    unittest.main()
