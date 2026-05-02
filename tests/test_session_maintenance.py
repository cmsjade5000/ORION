import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestSessionMaintenance(unittest.TestCase):
    def _script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "session_maintenance.py"

    def _write_fake_openclaw(
        self,
        root: Path,
        *,
        missing: int,
        before: int,
        after: int,
        reindex_exit_code: int = 0,
        reindex_stdout: str = "Memory index updated (main).",
        dreaming_enabled: bool = True,
    ) -> None:
        command_log = root / "command-log.txt"
        fake = root / "openclaw"
        fake.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
echo "$*" >> "{command_log}"
if [[ "$1 $2" == "sessions cleanup" ]]; then
  shift 2
  if printf '%s\\n' "$@" | grep -qx -- '--dry-run'; then
    cat <<'JSON'
[plugins] memory-lancedb: plugin registered
{{"agentId":"main","beforeCount":{before},"afterCount":{after},"missing":{missing},"wouldMutate":true}}
JSON
    exit 0
  fi
  if printf '%s\\n' "$@" | grep -qx -- '--enforce'; then
    cat <<'JSON'
{{"agentId":"main","beforeCount":{before},"afterCount":{after},"missing":{missing}}}
JSON
    exit 0
  fi
fi
if [[ "$1 $2" == "memory index" ]]; then
  shift 2
  echo "{reindex_stdout}"
  exit {reindex_exit_code}
fi
if [[ "${{1:-}} ${{2:-}} ${{3:-}}" == "config get plugins.entries.memory-core.config.dreaming.enabled" ]]; then
  echo "{str(dreaming_enabled).lower()}"
  exit 0
fi
if [[ "$1 $2" == "memory rem-backfill" ]]; then
  mkdir -p "{root}/memory/.dreams"
  cat > "{root}/memory/.dreams/short-term-recall.json" <<'JSON'
{{"updatedAt":"2026-05-02T16:02:55.185Z","entries":[{{"key":"daily:2026-04-06"}}]}}
JSON
  cat <<'JSON'
{{"writtenEntries":1,"stagedShortTermEntries":1}}
JSON
  exit 0
fi
if [[ "$1" == "doctor" ]]; then
  echo "doctor ok"
  exit 0
fi
echo "unexpected command: $*" >&2
exit 2
""",
            encoding="utf-8",
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def test_preview_only_writes_report_and_skips_apply(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root, missing=10, before=20, after=18)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["applied"])
            self.assertFalse(payload["memory_reindex"]["required"])
            self.assertIsNone(payload["memory_reindex"]["ok"])
            self.assertTrue((root / "tasks" / "NOTES" / "session-maintenance.md").exists())
            command_log = (root / "command-log.txt").read_text(encoding="utf-8")
            self.assertNotIn("memory index", command_log)
            self.assertNotIn("memory rem-backfill", command_log)

    def test_apply_requires_auto_ok_and_runs_when_thresholds_met(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            (root / "memory" / ".dreams").mkdir(parents=True, exist_ok=True)
            (root / "memory" / ".dreams" / "short-term-recall.json").write_text(
                '{"entries":[]}\n',
                encoding="utf-8",
            )
            (root / "memory" / "2026-04-06-gateway-update.md").write_text("# Session\n\nhello\n", encoding="utf-8")
            self._write_fake_openclaw(root, missing=120, before=200, after=50)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            env["AUTO_OK"] = "1"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--apply",
                    "--doctor",
                    "--min-missing",
                    "50",
                    "--min-reclaim",
                    "25",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["apply_allowed"])
            self.assertTrue(payload["applied"])
            self.assertTrue(payload["maintenance_ok"])
            self.assertTrue(payload["memory_reindex"]["required"])
            self.assertTrue(payload["memory_reindex"]["ok"])
            self.assertEqual(payload["doctor_exit_code"], 0)
            self.assertEqual(payload["consolidation_preview"]["planned"], 1)
            self.assertEqual(payload["consolidation_apply"]["result"]["merged"], 1)
            self.assertTrue((root / "memory" / "2026-04-06.md").exists())
            report = (root / "tasks" / "NOTES" / "session-maintenance.md").read_text(encoding="utf-8")
            self.assertIn("## Memory Reindex", report)
            self.assertIn("Memory index updated (main).", report)
            command_log = (root / "command-log.txt").read_text(encoding="utf-8").splitlines()
            self.assertIn("memory index --agent main --force", command_log)
            self.assertFalse(any("memory rem-backfill" in item for item in command_log))
            self.assertLess(
                command_log.index("memory index --agent main --force"),
                command_log.index("doctor --non-interactive"),
            )

    def test_apply_skips_reindex_when_consolidation_changed_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            (root / "memory" / ".dreams").mkdir(parents=True, exist_ok=True)
            (root / "memory" / ".dreams" / "short-term-recall.json").write_text(
                '{"entries":[]}\n',
                encoding="utf-8",
            )
            self._write_fake_openclaw(root, missing=120, before=200, after=50)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            env["AUTO_OK"] = "1"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--apply",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["applied"])
            self.assertFalse(payload["memory_reindex"]["required"])
            self.assertIsNone(payload["memory_reindex"]["ok"])
            command_log = (root / "command-log.txt").read_text(encoding="utf-8")
            self.assertNotIn("memory index --agent main --force", command_log)
            self.assertNotIn("memory rem-backfill", command_log)

    def test_apply_seeds_missing_dreaming_recall_even_below_cleanup_thresholds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            self._write_fake_openclaw(root, missing=1, before=20, after=19)
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            env["AUTO_OK"] = "1"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--apply",
                    "--min-missing",
                    "50",
                    "--min-reclaim",
                    "25",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["apply_allowed"])
            self.assertFalse(payload["applied"])
            self.assertTrue(payload["dreaming_recall"]["required"])
            self.assertTrue(payload["dreaming_recall"]["ok"])
            self.assertTrue(payload["memory_reindex"]["required"])
            self.assertTrue(payload["memory_reindex"]["ok"])
            command_log = (root / "command-log.txt").read_text(encoding="utf-8").splitlines()
            expected_backfill = (
                f"memory rem-backfill --agent main --path {root.resolve() / 'memory'} --stage-short-term --json"
            )
            self.assertIn(
                expected_backfill,
                command_log,
            )
            self.assertIn("memory index --agent main --force", command_log)
            report = (root / "tasks" / "NOTES" / "session-maintenance.md").read_text(encoding="utf-8")
            self.assertIn("## Dreaming Recall Store", report)
            self.assertIn("- seeded: `true`", report)

    def test_reindex_failure_is_reported_and_not_silent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            (root / "memory").mkdir(parents=True, exist_ok=True)
            (root / "memory" / "2026-04-06-gateway-update.md").write_text("# Session\n\nhello\n", encoding="utf-8")
            self._write_fake_openclaw(
                root,
                missing=120,
                before=200,
                after=50,
                reindex_exit_code=9,
                reindex_stdout="reindex failed",
            )
            env = dict(os.environ)
            env["PATH"] = f"{root}:{env.get('PATH', '')}"
            env["AUTO_OK"] = "1"
            result = subprocess.run(
                [
                    "python3",
                    str(self._script()),
                    "--repo-root",
                    str(root),
                    "--agent",
                    "main",
                    "--fix-missing",
                    "--apply",
                    "--json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["maintenance_ok"])
            self.assertEqual(payload["memory_reindex"]["exit_code"], 9)
            report = (root / "tasks" / "NOTES" / "session-maintenance.md").read_text(encoding="utf-8")
            self.assertIn("- ok: `false`", report)
            self.assertIn("reindex failed", report)


if __name__ == "__main__":
    unittest.main()
