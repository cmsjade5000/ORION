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

    def _write_fake_openclaw(self, root: Path, *, missing: int, before: int, after: int) -> None:
        fake = root / "openclaw"
        fake.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
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
            self.assertTrue((root / "tasks" / "NOTES" / "session-maintenance.md").exists())

    def test_apply_requires_auto_ok_and_runs_when_thresholds_met(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tasks" / "NOTES").mkdir(parents=True, exist_ok=True)
            (root / "memory").mkdir(parents=True, exist_ok=True)
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
            self.assertEqual(payload["doctor_exit_code"], 0)
            self.assertEqual(payload["consolidation_preview"]["planned"], 1)
            self.assertEqual(payload["consolidation_apply"]["result"]["merged"], 1)
            self.assertTrue((root / "memory" / "2026-04-06.md").exists())


if __name__ == "__main__":
    unittest.main()
