import json
import re
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

    def test_roster_and_routing_include_polaris(self):
        roster = self._read("agents/INDEX.md")
        routing = self._read("src/core/shared/ROUTING.md")
        orion = self._read("src/agents/ORION.md")

        self.assertIn("### POLARIS", roster)
        self.assertIn("POLARIS: admin co-pilot", routing)
        self.assertIn("delegate to POLARIS", orion)

    def test_inbox_and_contacts_scaffold_exist(self):
        inbox = self._read("tasks/INBOX/POLARIS.md")
        contacts = self._read("tasks/CONTACTS.md")

        self.assertIn("# POLARIS Inbox", inbox)
        self.assertIn("## Packets", inbox)
        self.assertIn("# Contact Registry (POLARIS)", contacts)
        self.assertIn("Last Touch (YYYY-MM-DD)", contacts)

    def test_config_and_docs_allowlist_include_polaris(self):
        cfg = json.loads(self._read("openclaw.json.example"))
        allow_agents = cfg["agents"]["list"][0]["subagents"]["allowAgents"]
        self.assertIn("polaris", allow_agents)

        migration = self._read("docs/OPENCLAW_CONFIG_MIGRATION.md")
        self.assertIn('"polaris"', migration)

    def test_dashboards_include_polaris(self):
        tg = self._read("src/plugins/telegram/dashboard/index.ts")
        mini = self._read("apps/telegram-miniapp-dashboard/server/index.js")

        self.assertIn('.text("POLARIS", "agent_POLARIS")', tg)
        self.assertIn('case "POLARIS":', tg)

        m = re.search(r"const PRIMARY_AGENTS = \[(.*?)\];", mini)
        self.assertIsNotNone(m)
        self.assertIn('"POLARIS"', m.group(1))

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
