import json
import unittest
from pathlib import Path


class TestAgentRosterIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]

    def _read(self, rel: str) -> str:
        return (self.repo / rel).read_text(encoding="utf-8")

    def test_polaris_role_exists(self):
        text = self._read("src/agents/POLARIS.md")
        self.assertIn("# Role Layer — POLARIS", text)
        self.assertIn("internal-only", text)

    def test_quest_role_exists(self):
        text = self._read("src/agents/QUEST.md")
        self.assertIn("# Role Layer — QUEST", text)
        self.assertIn("internal-only", text)
        self.assertIn("no longer part of the default ORION core routing surface", text)

    def test_roster_and_routing_include_polaris(self):
        roster = self._read("agents/INDEX.md")
        routing = self._read("src/core/shared/ROUTING.md")
        orion = self._read("src/agents/ORION.md")

        self.assertIn("### POLARIS", roster)
        self.assertIn("POLARIS: admin co-pilot", routing)
        self.assertIn("delegate to POLARIS", orion)

    def test_extension_lanes_are_explicitly_non_core(self):
        roster = self._read("agents/INDEX.md")
        routing = self._read("src/core/shared/ROUTING.md")
        orion = self._read("src/agents/ORION.md")

        self.assertIn("## Extension Lanes (Not Part Of Default ORION Core Routing)", roster)
        self.assertIn("### QUEST", roster)
        self.assertIn("### PIXEL", roster)
        self.assertIn("Non-Core Extension Lanes", routing)
        self.assertIn("do not route default daily work through PIXEL or QUEST", orion)

    def test_inbox_and_contacts_scaffold_exist(self):
        inbox = self._read("tasks/INBOX/POLARIS.md")
        contacts = self._read("tasks/CONTACTS.md")

        self.assertIn("# POLARIS Inbox", inbox)
        self.assertIn("## Packets", inbox)
        self.assertIn("# Contact Registry (POLARIS)", contacts)
        self.assertIn("Last Touch (YYYY-MM-DD)", contacts)

    def test_quest_inbox_scaffold_exists(self):
        inbox = self._read("tasks/INBOX/QUEST.md")
        self.assertIn("# QUEST Inbox", inbox)
        self.assertIn("## Packets", inbox)

    def test_config_and_docs_allowlist_include_polaris(self):
        cfg = json.loads(self._read("openclaw.json.example"))
        allow_agents = cfg["agents"]["list"][0]["subagents"]["allowAgents"]
        self.assertIn("polaris", allow_agents)

        migration = self._read("docs/OPENCLAW_CONFIG_MIGRATION.md")
        self.assertIn('"polaris"', migration)

    def test_config_and_docs_keep_extension_lanes_out_of_core_allowlist(self):
        cfg = json.loads(self._read("openclaw.json.example"))
        allow_agents = cfg["agents"]["list"][0]["subagents"]["allowAgents"]
        self.assertNotIn("quest", allow_agents)
        self.assertNotIn("pixel", allow_agents)

        migration = self._read("docs/OPENCLAW_CONFIG_MIGRATION.md")
        self.assertNotIn('"quest"', migration)
        self.assertNotIn('"pixel"', migration)

    def test_dashboards_include_polaris(self):
        tg = self._read("src/plugins/telegram/dashboard/index.ts")

        self.assertIn('.text("POLARIS", "agent_POLARIS")', tg)
        self.assertIn('case "POLARIS":', tg)

    def test_dashboard_stays_on_core_lanes(self):
        tg = self._read("src/plugins/telegram/dashboard/index.ts")

        self.assertIn('.text("WIRE", "agent_WIRE")', tg)
        self.assertIn('.text("SCRIBE", "agent_SCRIBE")', tg)
        self.assertNotIn('.text("QUEST", "agent_QUEST")', tg)
        self.assertNotIn('.text("PIXEL", "agent_PIXEL")', tg)
        self.assertNotIn('case "QUEST":', tg)
        self.assertNotIn('case "PIXEL":', tg)

    def test_ownership_matrix_and_queue_policy_links_exist(self):
        matrix = self._read("docs/AGENT_OWNERSHIP_MATRIX.md")
        hierarchy = self._read("docs/AGENT_HIERARCHY.md")
        orchestration = self._read("docs/ORION_SINGLE_BOT_ORCHESTRATION.md")
        polaris = self._read("src/agents/POLARIS.md")

        self.assertIn("| Workflow | Primary | Backup | Gatekeeper |", matrix)
        self.assertIn("Kalshi policy/risk/parameter changes", matrix)
        self.assertIn("docs/AGENT_OWNERSHIP_MATRIX.md", hierarchy)
        self.assertIn("docs/AGENT_OWNERSHIP_MATRIX.md", orchestration)
        self.assertIn("Max active packets: 8.", polaris)


if __name__ == "__main__":
    unittest.main()
