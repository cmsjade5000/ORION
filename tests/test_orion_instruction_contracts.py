import unittest
import json
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
        cls.heartbeat_text = (repo / "HEARTBEAT.md").read_text(encoding="utf-8")
        cls.atlas_role_text = (repo / "src" / "agents" / "ATLAS.md").read_text(encoding="utf-8")
        cls.task_packet_text = (repo / "docs" / "TASK_PACKET.md").read_text(encoding="utf-8")
        cls.survival_rules = {
            rule["id"]: rule
            for rule in json.loads(
                (repo / "src" / "core" / "shared" / "orion_survival_rules.json").read_text(
                    encoding="utf-8"
                )
            )["rules"]
        }

    def test_survival_rule_artifact_shape(self):
        for rule_id in ("R1", "R2", "R3", "R4", "R5", "R6"):
            self.assertIn(rule_id, self.survival_rules)
            self.assertIn("duplicate_phrase", self.survival_rules[rule_id])
            self.assertIn("required_in", self.survival_rules[rule_id])

    def test_cron_delegation_contract(self):
        self.assertIn("ATLAS delegation with a Task Packet", self.agents_text)
        self.assertIn("ORION may execute directly only when the task is simple, single-step, reversible", self.agents_text)
        self.assertIn("Direct execution criteria (all required):", self.agents_text)
        self.assertIn("not configured yet", self.agents_text)
        self.assertIn("HARD RULE: do not claim it is already configured.", self.orion_role_text)
        self.assertIn("Direct execution criteria (all required):", self.orion_role_text)
        rule = self.survival_rules["R1"]
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)

    def test_operational_change_verification_contract(self):
        self.assertIn(
            "Never claim an operational change is already complete unless it was executed + verified",
            self.routing_text,
        )
        self.assertIn("Never claim an operational change is already done", self.orion_role_text)
        rule = self.survival_rules["R2"]
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)

    def test_crisis_handoff_contract(self):
        self.assertIn("safety-first guidance, then hand off to EMBER (primary).", self.agents_text)
        self.assertIn("Give safety-first guidance (emergency services / 988 in the US).", self.orion_role_text)
        self.assertIn("hand off to EMBER (primary)", self.orion_role_text)
        rule = self.survival_rules["R3"]
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)

    def test_destructive_reset_contract(self):
        self.assertIn("explicit confirmation gate + propose a reversible first step", self.agents_text)
        self.assertIn("Ask for explicit confirmation.", self.orion_role_text)
        self.assertIn("reversible first step", self.orion_role_text)
        rule = self.survival_rules["R4"]
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)

    def test_announce_skip_contract(self):
        self.assertIn("Reply exactly `ANNOUNCE_SKIP`", self.agents_text)
        self.assertIn("Do not add any other text", self.agents_text)
        self.assertIn("After the announce prompt is satisfied, send a normal user-facing synthesis", self.agents_text)
        self.assertIn("reply with exactly `ANNOUNCE_SKIP`", self.orion_role_text)
        self.assertIn("After satisfying an announce prompt with `ANNOUNCE_SKIP`", self.orion_role_text)
        rule = self.survival_rules["R6"]
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)

    def test_explore_execute_contract(self):
        self.assertIn(
            'Explore vs execute: ask explicitly "explore" vs "execute" when user intent is ambiguous or impact is non-trivial.',
            self.agents_text,
        )
        rule = self.survival_rules["R5"]
        self.assertIn('Ask explicitly using the words: "explore" vs "execute"', self.orion_role_text)
        self.assertIn(rule["exact_phrase"], self.orion_role_text)
        self.assertIn("stop and wait for the one-word answer", self.orion_role_text)
        for rel in rule["required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["duplicate_phrase"], text)
        for rel in rule["exact_required_in"]:
            text = (Path(__file__).resolve().parents[1] / rel).read_text(encoding="utf-8")
            self.assertIn(rule["exact_phrase"], text)

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

    def test_notes_and_reminders_contract(self):
        self.assertIn("For Apple Notes requests", self.orion_role_text)
        self.assertIn(
            "use Notes capabilities first",
            self.orion_role_text,
        )
        self.assertIn(
            "never use repo `read`/`*.md` title lookup unless Cory explicitly asks for a repo file.",
            self.orion_role_text,
        )
        self.assertIn("For Apple Reminders requests, use Reminders capabilities first", self.orion_role_text)
        self.assertIn(
            "If Apple Notes lookup fails, ask Cory to paste or screenshot the note text",
            self.orion_role_text,
        )
        self.assertIn("For note-summary requests", self.orion_role_text)
        self.assertIn(
            "If a requested note is not found, do not propose creating a new note unless Cory explicitly asks to create one.",
            self.orion_role_text,
        )
        self.assertIn(
            "Treat reminders, notes capture, follow-through, daily agenda requests, and weekly review requests as POLARIS-first",
            self.orion_role_text,
        )

    def test_agentmail_identity_contract(self):
        self.assertIn("orion_gatewaybot@agentmail.to", self.orion_role_text)
        self.assertIn("AgentMail inbox identity, not a personal mailbox", self.orion_role_text)
        self.assertIn("Never answer that ORION has no email address.", self.orion_role_text)

    def test_ping_probe_contract(self):
        self.assertIn(
            "reply with exactly `ORION_OK` and nothing else.",
            self.orion_role_text,
        )
        self.assertIn(
            "timestamp-wrapped inbound line whose final token is exactly `Ping` or `ping`",
            self.orion_role_text,
        )

    def test_dreaming_command_contract(self):
        self.assertIn("If a user message begins with `/dreaming`", self.orion_role_text)
        self.assertIn("/dreaming` or `/dreaming status` -> run `python3 scripts/assistant_status.py --cmd dreaming-status --json`", self.orion_role_text)
        self.assertIn("/dreaming on` -> run `python3 scripts/assistant_status.py --cmd dreaming-on --json`", self.orion_role_text)
        self.assertIn("/dreaming off` -> run `python3 scripts/assistant_status.py --cmd dreaming-off --json`", self.orion_role_text)

    def test_heartbeat_file_disambiguates_user_ping(self):
        self.assertIn("INTERNAL_HEARTBEAT_POLL_V1", self.heartbeat_text)
        self.assertIn("Never treat normal user-authored messages such as `Ping`, `ping`, `Everything ok?`", self.heartbeat_text)
        self.assertIn("For non-heartbeat user messages, ignore this file", self.heartbeat_text)
        self.assertIn("reply exactly `HEARTBEAT_OK`", self.heartbeat_text)

    def test_verifiable_capability_claims_contract(self):
        self.assertIn("Only claim capabilities you can verify in-turn.", self.orion_role_text)
        self.assertIn("Never emit raw `<tool_code>`", self.orion_role_text)
        self.assertIn("Never emit raw `<error>` blocks", self.orion_role_text)
        self.assertIn("JSON error injected into SSE stream", self.orion_role_text)
        self.assertIn("do not dump raw CLI JSON into the reply path", self.orion_role_text)
        self.assertIn("Never surface raw gateway/CLI diagnostics, cron internals, or JSON blobs", self.orion_role_text)
        self.assertIn("Mac control capability question:", self.orion_role_text)

    def test_tool_execution_contracts(self):
        self.assertIn("Execution Mode", self.orion_role_text)
        self.assertIn("Tool Scope", self.orion_role_text)
        self.assertIn("transcript-aware runtimes", self.orion_role_text)
        self.assertIn("request_permissions", self.orion_role_text)
        self.assertIn("@plugin", self.orion_role_text)
        self.assertIn("mcp-first", self.orion_role_text)
        self.assertIn("sessions_spawn` -> `sessions_yield`", self.orion_role_text)
        self.assertIn("Keep ORION non-recursive", self.orion_role_text)
        self.assertIn("subagents steer", self.orion_role_text)

    def test_atlas_recursive_orchestration_contract(self):
        self.assertIn("ATLAS is the only recursive orchestrator in ORION core.", self.atlas_role_text)
        self.assertIn("sessions_spawn` -> `sessions_yield`", self.atlas_role_text)
        self.assertIn("subagents list", self.atlas_role_text)
        self.assertIn("subagents steer", self.atlas_role_text)
        self.assertIn("subagents kill", self.atlas_role_text)
        self.assertIn("Do not use recursive orchestration for speculative fan-out", self.atlas_role_text)
        self.assertIn("skills/mcporter/SKILL.md", self.orion_role_text)
        self.assertIn("config/mcporter.json", self.orion_role_text)
        self.assertIn("must not expose raw MCP payloads", self.orion_role_text)
        self.assertIn("parallel tool calls only for independent, non-destructive checks", self.orion_role_text)
        self.assertIn("Tool orchestration rules:", self.atlas_role_text)
        self.assertIn("multi_tool_use.parallel", self.atlas_role_text)
        self.assertIn("spawn_agents_on_csv", self.atlas_role_text)

    def test_new_skill_routing_contracts(self):
        self.assertIn("skills/social-intelligence/SKILL.md", self.orion_role_text)
        self.assertIn("auth is missing, say setup is required", self.orion_role_text)
        self.assertIn("skills/phone-voice/SKILL.md", self.orion_role_text)
        self.assertIn("treat it as a setup project until the bridge, tunnel, and provider credentials are verified", self.orion_role_text)
        self.assertIn("skills/postgres-job-queue/SKILL.md", self.orion_role_text)

    def test_task_packet_tool_fields_contract(self):
        self.assertIn("transcript-aware runtimes", self.task_packet_text)
        self.assertIn("Execution Mode:", self.task_packet_text)
        self.assertIn("Tool Scope:", self.task_packet_text)
        self.assertIn("Retrieval Order:", self.task_packet_text)
        self.assertIn("Evidence Required:", self.task_packet_text)
        self.assertIn("Rollback:", self.task_packet_text)

    def test_survival_rules_present_in_soul_head(self):
        soul = _compose_soul("ORION")
        head = soul[:17500]
        for rule in self.survival_rules.values():
            self.assertIn(rule["soul_head_phrase"], head)
        self.assertIn("HARD RULE: do not claim it is already configured", head)
        self.assertIn("Ask for explicit confirmation.", head)


if __name__ == "__main__":
    unittest.main()
