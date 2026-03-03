import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "stop_gate_enforcer.py"
    spec = importlib.util.spec_from_file_location("stop_gate_enforcer", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


class TestStopGateEnforcer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load_module()

    def _write_reliability(
        self,
        history_dir: Path,
        stamp: str,
        generated_at: str,
        lane_wait_count: int,
        lane_wait_p95_ms: int,
    ) -> None:
        path = history_dir / f"reliability-{stamp}.json"
        payload = {
            "generated_at": generated_at,
            "lane_wait_24h": {"count": lane_wait_count, "p95_ms": lane_wait_p95_ms},
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_jobs(self, jobs_path: Path, jobs: list[dict]) -> None:
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(json.dumps({"jobs": jobs}, indent=2) + "\n", encoding="utf-8")

    def test_no_trigger_when_not_enough_days(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            history_dir = tmp / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            jobs_path = tmp / "cron" / "jobs.json"
            out_json = tmp / "stop-gate.json"
            out_md = tmp / "stop-gate.md"

            self._write_reliability(
                history_dir,
                stamp="20260302-120000",
                generated_at="2026-03-02T17:00:00+00:00",
                lane_wait_count=21,
                lane_wait_p95_ms=34034,
            )
            self._write_jobs(
                jobs_path,
                jobs=[
                    {"id": "j1", "name": "party-batch-tonight-r4h", "enabled": True},
                    {"id": "j2", "name": "orion-route-hygiene-daily", "enabled": True},
                ],
            )

            argv = [
                "stop_gate_enforcer.py",
                "--history-dir",
                str(history_dir),
                "--jobs-path",
                str(jobs_path),
                "--output-json",
                str(out_json),
                "--output-md",
                str(out_md),
                "--consecutive-days",
                "2",
                "--apply",
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.m.main()

            self.assertEqual(rc, 0)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertFalse(report["triggered"])
            self.assertEqual(report["disabled_job_ids"], [])

            jobs_after = json.loads(jobs_path.read_text(encoding="utf-8"))
            enabled_map = {j["id"]: j["enabled"] for j in jobs_after["jobs"]}
            self.assertTrue(enabled_map["j1"])
            self.assertTrue(enabled_map["j2"])

    def test_trigger_disables_matching_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            history_dir = tmp / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            jobs_path = tmp / "cron" / "jobs.json"
            out_json = tmp / "stop-gate.json"
            out_md = tmp / "stop-gate.md"

            self._write_reliability(
                history_dir,
                stamp="20260301-120000",
                generated_at="2026-03-01T17:00:00+00:00",
                lane_wait_count=15,
                lane_wait_p95_ms=22000,
            )
            self._write_reliability(
                history_dir,
                stamp="20260302-120000",
                generated_at="2026-03-02T17:00:00+00:00",
                lane_wait_count=19,
                lane_wait_p95_ms=18000,
            )
            self._write_jobs(
                jobs_path,
                jobs=[
                    {"id": "j1", "name": "party-batch-tonight-r4h", "enabled": True},
                    {"id": "j2", "name": "orion-route-hygiene-daily", "enabled": True},
                    {"id": "j3", "name": "canary-promote-openprose", "enabled": True},
                ],
            )

            argv = [
                "stop_gate_enforcer.py",
                "--history-dir",
                str(history_dir),
                "--jobs-path",
                str(jobs_path),
                "--output-json",
                str(out_json),
                "--output-md",
                str(out_md),
                "--consecutive-days",
                "2",
                "--apply",
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.m.main()

            self.assertEqual(rc, 0)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(report["triggered"])
            self.assertCountEqual(report["disabled_job_ids"], ["j1", "j3"])

            jobs_after = json.loads(jobs_path.read_text(encoding="utf-8"))
            enabled_map = {j["id"]: j["enabled"] for j in jobs_after["jobs"]}
            self.assertFalse(enabled_map["j1"])
            self.assertTrue(enabled_map["j2"])
            self.assertFalse(enabled_map["j3"])

            backups = list((tmp / "cron").glob("jobs.json.bak.stopgate.*"))
            self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
