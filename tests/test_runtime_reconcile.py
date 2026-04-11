import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestRuntimeReconcile(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "runtime_reconcile.py"

    def _write_fake_openclaw(self, root: Path) -> None:
        fake = root / "openclaw"
        log = root / "command-log.txt"
        fake.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{log}"
if [[ "$1 $2 $3" == "tasks list --json" ]]; then
  cat <<'JSON'
{{"tasks":[{{"label":"assistant-task-loop","status":"lost","error":"backing session missing"}}]}}
JSON
  exit 0
fi
if [[ "$1 $2 $3" == "tasks audit --json" ]]; then
  cat <<'JSON'
{{"summary":{{"byCode":{{"inconsistent_timestamps":1}}}},"findings":[{{"code":"stale_running","detail":"stuck"}}]}}
JSON
  exit 0
fi
if [[ "$1 $2 $3" == "tasks maintenance --apply" ]]; then
  cat <<'JSON'
{{"ok":true,"applied":true}}
JSON
  exit 0
fi
if [[ "$1 $2" == "sessions cleanup" ]]; then
  cat <<'JSON'
{{"ok":true,"missing":1}}
JSON
  exit 0
fi
if [[ "$1 $2 $3" == "channels status --probe" ]]; then
  cat <<'JSON'
{{"channels":{{"discord":{{"configured":true,"running":false,"lastError":"Unknown system error -11: read","probe":{{"ok":true}}}}}},"channelAccounts":{{"discord":[{{"running":false,"lastError":"Unknown system error -11: read","reconnectAttempts":5}}]}}}}
JSON
  exit 0
fi
if [[ "$1 $2" == "channels logs" ]]; then
  cat <<'JSON'
{{"lines":[{{"msg":"stale socket"}}]}}
JSON
  exit 0
fi
if [[ "$1 $2" == "gateway restart" ]]; then
  cat <<'JSON'
{{"ok":true}}
JSON
  exit 0
fi
echo "unexpected: $*" >&2
exit 2
""",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        scripts_dir = root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        repair = scripts_dir / "task_registry_repair.py"
        repair.write_text(
            """#!/usr/bin/env python3
import json
print(json.dumps({"ok": True, "applied": True}))
""",
            encoding="utf-8",
        )
        repair.chmod(repair.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def test_preview_collects_findings_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["tasks"]["lost_backing_session"], 1)
            self.assertEqual(payload["tasks"]["stale_running"], 1)
            self.assertEqual(payload["tasks"]["inconsistent_timestamps"], 1)
            self.assertTrue(payload["discord"]["needs_restart"])
            self.assertEqual([item["kind"] for item in payload["actions"]], ["discord-logs"])

    def test_apply_runs_bounded_remediations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            result = subprocess.run(
                ["python3", str(self._script()), "--repo-root", str(root), "--apply", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            kinds = [item["kind"] for item in payload["actions"]]
            self.assertEqual(
                kinds,
                ["tasks-maintenance", "sessions-cleanup", "task-registry-repair", "discord-logs", "gateway-restart"],
            )
            report = (root / "tasks" / "NOTES" / "runtime-reconcile.md").read_text(encoding="utf-8")
            self.assertIn("gateway-restart", report)
            command_log = (root / "command-log.txt").read_text(encoding="utf-8")
            self.assertIn("tasks maintenance --apply --json", command_log)
            self.assertIn("sessions cleanup --agent main --enforce --fix-missing --json", command_log)
            self.assertIn("gateway restart --json", command_log)


if __name__ == "__main__":
    unittest.main()
