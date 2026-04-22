import unittest
from pathlib import Path


class TestOrionAgentToolingRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.skills_doc = (cls.repo / "docs" / "ASSISTANT_SKILLS.md").read_text(encoding="utf-8")
        cls.routing = (cls.repo / "src" / "core" / "shared" / "ROUTING.md").read_text(
            encoding="utf-8"
        )
        cls.roster = (cls.repo / "agents" / "INDEX.md").read_text(encoding="utf-8")
        cls.pilots = (cls.repo / "docs" / "ORION_TOOL_PILOTS_2026_04.md").read_text(
            encoding="utf-8"
        )
        cls.sweep = (cls.repo / "docs" / "ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md").read_text(
            encoding="utf-8"
        )
        cls.acpx_doc = (cls.repo / "docs" / "ATLAS_ACPX_PILOT.md").read_text(encoding="utf-8")

    def test_skill_matrix_covers_core_agents(self):
        for needle in (
            "## ORION",
            "`mcporter`",
            "`task-packet-guard`",
            "`agentmail`",
            "`session-logs`",
            "`clawhub`",
            "## ATLAS",
            "`system-metrics`",
            "`gateway-service`",
            "`policy-gate-conftest`",
            "`secure-code-preflight`",
            "## WIRE",
            "## POLARIS",
            "## SCRIBE",
            "## NODE",
            "## PULSE",
            "## STRATUS",
        ):
            self.assertIn(needle, self.skills_doc)

    def test_routing_split_is_explicit(self):
        self.assertIn("delegate to WIRE first", self.routing)
        self.assertIn("Discovery or gaming requests are off-core extension work", self.routing)
        self.assertIn("PIXEL scouts; WIRE validates current external facts; ATLAS owns implementation/execution.", self.roster)

    def test_disabled_surfaces_remain_pilots(self):
        for needle in (
            "ACPX Specialist Pilot",
            "Firecrawl",
            "browser` plugin: defer",
            "What Remains Deferred",
        ):
            self.assertTrue(needle in self.pilots or needle in self.sweep)

    def test_acpx_live_policy_is_bounded_and_smoke_tested(self):
        for needle in (
            "ATLAS owns the live ACPX lane",
            "native subagents stay default",
            "no direct user-facing ACPX usage",
            "pluginToolsMcpBridge=false",
            "permissionMode=approve-reads",
            "nonInteractivePermissions=fail",
            "scripts/acpx_runtime_smoke.py",
        ):
            self.assertTrue(needle in self.acpx_doc or needle in self.pilots or needle in self.skills_doc)


if __name__ == "__main__":
    unittest.main()
