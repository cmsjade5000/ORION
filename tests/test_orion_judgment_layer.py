import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestOrionJudgmentLayer(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "orion_judgment_layer.py"

    def _write_bundle(self, root: Path, *, degraded: int = 0, approval_timeouts: int = 0, stale_task_runs: int = 0) -> Path:
        bundle = {
            "generated_at_utc": "2026-04-07T15:00:00Z",
            "gateway": {"health_ok": True, "config_audit_ok": True, "health_message": "ok"},
            "channels": {"degraded": degraded},
            "signals": {
                "approval_timeouts": approval_timeouts,
                "stale_task_runs": stale_task_runs,
                "discord_stale_socket_restarts": 0,
                "telegram_ipv4_fallbacks": 0,
                "exec_elevation_failures": 0,
            },
            "tasks": {"audit_ok": True, "list_ok": True},
            "codex_ready": True,
            "artifacts": {"summary_json": str(root / "tmp" / "orion_incident_bundle_latest.json")},
        }
        path = root / "tmp" / "bundle.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
        return path

    def test_write_latest_creates_latest_and_history_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ops").mkdir(parents=True, exist_ok=True)
            (root / "ops" / "judgment-policy.v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "orion.judgment-policy.v1",
                        "severity_to_recommendation": {"S1": "alert", "S2": "alert", "S3": "digest", "S4": "log-only"},
                        "notification_policy": {"cooldown_seconds": {"alert": 21600, "digest": 43200, "log-only": 0}},
                        "digest_policy": {"enabled": True, "min_severity": "S3"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            bundle = self._write_bundle(root)
            env = dict(os.environ)
            env["ORION_JUDGMENT_NOTIFY_DRY_RUN"] = "1"
            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--bundle", str(bundle), "--write-latest", "--json"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            latest_json = root / "tmp" / "orion_judgment_latest.json"
            latest_md = root / "tasks" / "NOTES" / "orion-judgment.md"
            history_json = list((root / "eval" / "history").glob("orion-judgment-*.json"))
            history_md = list((root / "eval" / "history").glob("orion-judgment-*.md"))
            self.assertTrue(latest_json.exists())
            self.assertTrue(latest_md.exists())
            self.assertTrue(history_json)
            self.assertTrue(history_md)

    def test_digest_recommendation_does_not_attempt_notification(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ops").mkdir(parents=True, exist_ok=True)
            (root / "ops" / "judgment-policy.v1.json").write_text(
                json.dumps(
                    {
                        "schema_version": "orion.judgment-policy.v1",
                        "severity_to_recommendation": {"S1": "alert", "S2": "alert", "S3": "digest", "S4": "log-only"},
                        "notification_policy": {"cooldown_seconds": {"alert": 21600, "digest": 43200, "log-only": 0}},
                        "digest_policy": {"enabled": True, "min_severity": "S3"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            bundle = self._write_bundle(root, degraded=1)
            env = dict(os.environ)
            env["ORION_JUDGMENT_NOTIFY_DRY_RUN"] = "1"
            proc = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--bundle", str(bundle), "--json"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["delivery"]["recommendation"], "digest")
            self.assertFalse(payload["notification"]["attempted"])
            self.assertEqual(payload["notification"]["reason"], "recommendation-not-alert")


if __name__ == "__main__":
    unittest.main()
