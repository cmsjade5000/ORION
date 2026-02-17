import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


def _load_validator():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "validate_task_packets.py"
    spec = importlib.util.spec_from_file_location("validate_task_packets", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


VALID_PACKET = """\
TASK_PACKET v1
Owner: {owner}
Requester: {requester}
Objective: Do a thing.
Success Criteria:
- It worked.
Constraints:
- Read-only.
Inputs:
- (none)
Risks:
- low
Stop Gates:
- Any destructive command.
Output Format:
- Short checklist.
"""


class TestValidateTaskPackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = _load_validator()

    def _write_inbox(self, agent: str, packets_md: str) -> tuple[str, tempfile.TemporaryDirectory]:
        td = tempfile.TemporaryDirectory()
        path = str(Path(td.name) / f"{agent}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {agent} Inbox\n\n## Packets\n")
            f.write(packets_md)
        return path, td

    def test_node_allows_atlas_requester(self):
        pkt = VALID_PACKET.format(owner="NODE", requester="ATLAS")
        path, td = self._write_inbox("NODE", pkt)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertEqual(errs, [])

    def test_node_blocks_orion_without_emergency(self):
        pkt = VALID_PACKET.format(owner="NODE", requester="ORION")
        path, td = self._write_inbox("NODE", pkt)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertTrue(any("Requester" in e for e in errs), errs)

    def test_node_allows_orion_with_emergency_bypass(self):
        pkt = (
            "TASK_PACKET v1\n"
            "Owner: NODE\n"
            "Requester: ORION\n"
            "Emergency: ATLAS_UNAVAILABLE\n"
            "Incident: INC-TEST-1\n"
            "Objective: Do a thing.\n"
            "Success Criteria:\n"
            "- It worked.\n"
            "Constraints:\n"
            "- Read-only.\n"
            "Inputs:\n"
            "- (none)\n"
            "Risks:\n"
            "- low\n"
            "Stop Gates:\n"
            "- Any destructive command.\n"
            "Output Format:\n"
            "- Short checklist.\n"
        )
        path, td = self._write_inbox("NODE", pkt)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertEqual(errs, [])

    def test_node_blocks_emergency_without_incident(self):
        pkt = (
            "TASK_PACKET v1\n"
            "Owner: NODE\n"
            "Requester: ORION\n"
            "Emergency: ATLAS_UNAVAILABLE\n"
            "Objective: Do a thing.\n"
            "Success Criteria:\n"
            "- It worked.\n"
            "Constraints:\n"
            "- Read-only.\n"
            "Inputs:\n"
            "- (none)\n"
            "Risks:\n"
            "- low\n"
            "Stop Gates:\n"
            "- Any destructive command.\n"
            "Output Format:\n"
            "- Short checklist.\n"
        )
        path, td = self._write_inbox("NODE", pkt)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertTrue(any("Incident" in e for e in errs), errs)

    def test_notify_allows_known_channels_and_blocks_unknown(self):
        ok = (
            "TASK_PACKET v1\n"
            "Owner: PIXEL\n"
            "Requester: ORION\n"
            "Notify: telegram,discord\n"
            "Objective: Do a thing.\n"
            "Success Criteria:\n"
            "- It worked.\n"
            "Constraints:\n"
            "- Read-only.\n"
            "Inputs:\n"
            "- (none)\n"
            "Risks:\n"
            "- low\n"
            "Stop Gates:\n"
            "- Any destructive command.\n"
            "Output Format:\n"
            "- Short checklist.\n"
        )
        path, td = self._write_inbox("PIXEL", ok)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertEqual(errs, [])

        bad = ok.replace("telegram,discord", "telegram,sms")
        path, td = self._write_inbox("PIXEL", bad)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertTrue(any("Notify" in e for e in errs), errs)

    def test_pixel_requires_orion(self):
        pkt = VALID_PACKET.format(owner="PIXEL", requester="ATLAS")
        path, td = self._write_inbox("PIXEL", pkt)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertTrue(any("Requester" in e for e in errs), errs)

    def test_ignores_fenced_examples(self):
        body = textwrap.dedent(
            """\
            ```text
            TASK_PACKET v1
            Owner: NODE
            Requester: ATLAS
            Objective: Example only.
            ```
            """
        )
        path, td = self._write_inbox("NODE", body)
        errs = self.v.validate_inbox_file(path)
        td.cleanup()
        self.assertEqual(errs, [])
