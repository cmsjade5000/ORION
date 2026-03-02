import unittest
from pathlib import Path


def _compose_soul(agent: str) -> str:
    repo = Path(__file__).resolve().parents[1]
    shared_dir = repo / "src" / "core" / "shared"
    roles_dir = repo / "src" / "agents"
    user_md = repo / "USER.md"

    shared_layers = ["CONSTITUTION.md", "USER.md", "FOUNDATION.md", "ROUTING.md"]

    parts: list[str] = []
    parts.append(f"# SOUL.md — {agent}")
    parts.append("")
    parts.append("**Generated:** TEST")
    parts.append(f"**Source:** src/core/shared + USER.md + src/agents/{agent}.md")
    parts.append("")
    parts.append("---")
    parts.append("")

    for f in shared_layers:
        parts.append(f"<!-- BEGIN shared/{f} -->")
        if f == "USER.md":
            parts.append(user_md.read_text(encoding="utf-8").rstrip())
        else:
            parts.append((shared_dir / f).read_text(encoding="utf-8").rstrip())
        parts.append("")
        parts.append(f"<!-- END shared/{f} -->")
        parts.append("")
        parts.append("---")
        parts.append("")

    parts.append(f"<!-- BEGIN roles/{agent}.md -->")
    parts.append((roles_dir / f"{agent}.md").read_text(encoding="utf-8").rstrip())
    parts.append("")
    parts.append(f"<!-- END roles/{agent}.md -->")
    parts.append("")

    return "\n".join(parts)


class TestOrionInstructionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[1]
        cls.agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
        cls.routing_text = (repo / "src" / "core" / "shared" / "ROUTING.md").read_text(
            encoding="utf-8"
        )
        cls.orion_role_text = (repo / "src" / "agents" / "ORION.md").read_text(encoding="utf-8")

    def test_cron_delegation_contract(self):
        self.assertIn("ATLAS delegation with a Task Packet", self.agents_text)
        self.assertIn("ORION may execute directly only when the task is simple, single-step, reversible", self.agents_text)
        self.assertIn("Direct execution criteria (all required):", self.agents_text)
        self.assertIn("not configured yet", self.agents_text)
        self.assertIn("HARD RULE: do not claim it is already configured.", self.orion_role_text)
        self.assertIn("Direct execution criteria (all required):", self.orion_role_text)

    def test_operational_change_verification_contract(self):
        self.assertIn(
            "Never claim an operational change is already complete unless it was executed + verified",
            self.routing_text,
        )
        self.assertIn("Never claim an operational change is already done", self.orion_role_text)

    def test_crisis_handoff_contract(self):
        self.assertIn("safety-first guidance, then hand off to EMBER (primary).", self.agents_text)
        self.assertIn("Give safety-first guidance (emergency services / 988 in the US).", self.orion_role_text)
        self.assertIn("hand off to EMBER (primary)", self.orion_role_text)

    def test_destructive_reset_contract(self):
        self.assertIn("explicit confirmation gate + propose a reversible first step", self.agents_text)
        self.assertIn("Ask for explicit confirmation.", self.orion_role_text)
        self.assertIn("reversible first step", self.orion_role_text)

    def test_announce_skip_contract(self):
        self.assertIn("Reply exactly `ANNOUNCE_SKIP`", self.agents_text)
        self.assertIn("Do not add any other text", self.agents_text)
        self.assertIn("After the announce prompt is satisfied, send a normal user-facing synthesis", self.agents_text)
        self.assertIn("reply with exactly `ANNOUNCE_SKIP`", self.orion_role_text)
        self.assertIn("After satisfying an announce prompt with `ANNOUNCE_SKIP`", self.orion_role_text)

    def test_explore_execute_contract(self):
        self.assertIn(
            'Explore vs execute: ask explicitly "explore" vs "execute" when user intent is ambiguous or impact is non-trivial.',
            self.agents_text,
        )
        self.assertIn('Ask explicitly using the words: "explore" vs "execute"', self.orion_role_text)

    def test_proactive_clarification_contract(self):
        self.assertIn(
            "ORION may ask one proactive clarifying question when ambiguity is likely to cause avoidable rework",
            self.agents_text,
        )
        self.assertIn(
            "You may ask one proactive clarifying question outside hard gates when ambiguity is likely to cause avoidable rework.",
            self.orion_role_text,
        )

    def test_progress_state_contract(self):
        self.assertIn("report it as `queued`, `in progress`, or `pending verification`", self.agents_text)
        self.assertIn("use explicit progress states: `queued`, `in progress`, or `pending verification`", self.orion_role_text)

    def test_survival_rules_present_in_soul_head(self):
        soul = _compose_soul("ORION")
        head = soul[:17500]
        self.assertIn("delegate to ATLAS with a Task Packet", head)
        self.assertIn("Never claim an operational change is already complete", head)
        self.assertIn("HARD RULE: do not claim it is already configured", head)
        self.assertIn("Give safety-first guidance", head)
        self.assertIn("Ask for explicit confirmation.", head)
        self.assertIn("reversible first step", head)
        self.assertIn("ANNOUNCE_SKIP", head)


if __name__ == "__main__":
    unittest.main()
