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


class TestSoulSizeBudget(unittest.TestCase):
    def test_orion_soul_under_injection_budget(self):
        # OpenClaw previously truncated SOUL.md at ~18k chars for ORION.
        # Budget slightly below that to keep headroom for small edits.
        soul = _compose_soul("ORION")
        self.assertLessEqual(len(soul), 17500)

        head = soul[:17500]
        self.assertIn("Never claim an operational change is already complete", head)
        self.assertIn("HARD RULE: do not claim it is already configured", head)

