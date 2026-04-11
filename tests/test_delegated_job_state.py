from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "delegated_job_state.py"
    spec = importlib.util.spec_from_file_location("delegated_job_state", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestDelegatedJobState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_write_job_artifacts_tolerates_raced_cleanup_unlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            jobs_dir = root / "tasks" / "JOBS"
            jobs_dir.mkdir(parents=True, exist_ok=True)
            stale_path = jobs_dir / "wf-ik-stale.json"
            stale_path.write_text("{}", encoding="utf-8")

            packet = SimpleNamespace(
                fields={"Owner": "ATLAS", "Requester": "ORION", "Objective": "Test workflow."},
                inbox_path=root / "tasks" / "INBOX" / "ATLAS.md",
                display_path="tasks/INBOX/ATLAS.md",
                start_line=4,
                lines=["TASK_PACKET v1", "Owner: ATLAS", "Requester: ORION", "Objective: Test workflow."],
                result_status=None,
                ticket_refs=[],
                pending_key="pending:test",
                packet_id="pkt-root",
                parent_packet_id="",
                root_packet_id="pkt-root",
                workflow_id="pkt-root",
            )

            real_unlink = Path.unlink

            def _flaky_unlink(path_obj: Path, *args, **kwargs):
                if path_obj.name == stale_path.name:
                    raise FileNotFoundError(path_obj)
                return real_unlink(path_obj, *args, **kwargs)

            with mock.patch.object(Path, "unlink", autospec=True, side_effect=_flaky_unlink):
                records = self.mod.write_job_artifacts(
                    repo_root=root,
                    packets=[packet],
                    ticket_map={},
                    pending_since_by_key={},
                    stale_threshold_hours=24.0,
                    now_ts=1700000000.0,
                )

            self.assertEqual(len(records), 1)
            summary = json.loads((jobs_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["workflow_count"], 1)


if __name__ == "__main__":
    unittest.main()
