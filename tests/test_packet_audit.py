from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "packet_audit.py"
    spec = importlib.util.spec_from_file_location("packet_audit", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestPacketAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = _load_module()

    def _write_inbox(self, root: Path, owner: str, body: str) -> Path:
        inbox = root / "tasks" / "INBOX" / f"{owner}.md"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(f"# {owner} Inbox\n\n## Packets\n{body.rstrip()}\n", encoding="utf-8")
        return inbox

    def _write_summary_for_visible_packets(self, root: Path) -> None:
        jobs = root / "tasks" / "JOBS"
        jobs.mkdir(parents=True, exist_ok=True)
        packets = self.audit.load_packets(root)
        jobs_payload = [{"job_id": self.audit._packet_job_id(packet)} for packet in packets]
        (jobs / "summary.json").write_text(json.dumps({"jobs": jobs_payload}, indent=2) + "\n", encoding="utf-8")

    def _codes(self, root: Path) -> list[str]:
        report = self.audit.audit_packets(root)
        return [str(issue["code"]) for issue in report["issues"]]

    def test_clean_fixture_returns_ok(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_inbox(
                root,
                "ATLAS",
                "\n".join(
                    [
                        "TASK_PACKET v1",
                        "Owner: ATLAS",
                        "Requester: ORION",
                        "Idempotency Key: clean-one",
                        "Packet ID: pkt-clean-one",
                        "Objective: Recover stale delegated workflow for gateway work.",
                        "Result:",
                        "Status: OK",
                    ]
                ),
            )
            self._write_summary_for_visible_packets(root)

            report = self.audit.audit_packets(root)

            self.assertTrue(report["ok"], report)
            self.assertEqual(report["issue_count"], 0)

    def test_duplicate_idempotency_key_across_inboxes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet = "\n".join(
                [
                    "TASK_PACKET v1",
                    "Owner: ATLAS",
                    "Requester: ORION",
                    "Idempotency Key: dup-key",
                    "Objective: Recover stale delegated workflow for gateway work.",
                ]
            )
            self._write_inbox(root, "ATLAS", packet)
            self._write_inbox(root, "ORION", packet.replace("Owner: ATLAS", "Owner: ORION"))

            self.assertIn("duplicate_identity", self._codes(root))

    def test_duplicate_packet_id_with_different_idempotency_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_inbox(
                root,
                "ATLAS",
                "\n\n".join(
                    [
                        "TASK_PACKET v1\nOwner: ATLAS\nRequester: ORION\nIdempotency Key: key-a\nPacket ID: pkt-dup\nObjective: Recover stale delegated workflow A.",
                        "TASK_PACKET v1\nOwner: ATLAS\nRequester: ORION\nIdempotency Key: key-b\nPacket ID: pkt-dup\nObjective: Recover stale delegated workflow B.",
                    ]
                ),
            )

            self.assertIn("duplicate_identity", self._codes(root))

    def test_generated_recovery_packet_missing_lineage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_inbox(
                root,
                "ATLAS",
                "TASK_PACKET v1\nOwner: ATLAS\nRequester: ORION\nIdempotency Key: recovery:stale:pkt-root\nObjective: Recover stale delegated workflow.",
            )

            self.assertIn("missing_generated_lineage", self._codes(root))

    def test_pending_recovery_descendant_with_terminal_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_inbox(
                root,
                "ATLAS",
                "\n\n".join(
                    [
                        "TASK_PACKET v1\nOwner: ATLAS\nRequester: ORION\nPacket ID: pkt-root\nObjective: Source work.\nResult:\nStatus: OK",
                        "TASK_PACKET v1\nOwner: ATLAS\nRequester: ORION\nIdempotency Key: recovery:stale:pkt-root\nPacket ID: pkt-recovery\nParent Packet ID: pkt-root\nRoot Packet ID: pkt-root\nWorkflow ID: pkt-root\nObjective: Recover stale delegated workflow.",
                    ]
                ),
            )

            self.assertIn("terminal_source_active_descendant", self._codes(root))

    def test_json_output_contains_stable_codes_and_locations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_inbox(
                root,
                "POLARIS",
                "TASK_PACKET v1\nOwner: POLARIS\nRequester: ORION\nObjective: Execute cron reminder workflow and verify it.",
            )
            script = Path(__file__).resolve().parents[1] / "scripts" / "packet_audit.py"
            proc = subprocess.run(
                ["python3", str(script), "--repo-root", str(root), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("route_mismatch", [issue["code"] for issue in payload["issues"]])
            first = payload["issues"][0]
            self.assertIn("path", first)
            self.assertIn("line", first)


if __name__ == "__main__":
    unittest.main()
