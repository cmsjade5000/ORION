import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestStratusHealthcheck(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _script_path(self) -> Path:
        return self._repo_root() / "scripts" / "stratus_healthcheck.sh"

    def _write_fake_openclaw(self, td: tempfile.TemporaryDirectory, *, health_ok: bool) -> Path:
        p = Path(td.name) / "openclaw"
        body = f"""#!/usr/bin/env bash
set -euo pipefail
cmd="${{1-}}"
shift || true
case "$cmd" in
  health)
    echo "simulated health"
    {"exit 0" if health_ok else "exit 1"}
    ;;
  gateway)
    sub="${{1-}}"
    if [[ "$sub" == "status" ]]; then
      echo "simulated gateway status"
      exit 0
    fi
    ;;
esac
echo "unknown command" >&2
exit 2
"""
        p.write_text(body, encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return p

    def test_ok_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=True)
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            r = subprocess.run(
                [str(self._script_path()), "--no-host"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            td.cleanup()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("gateway health: OK", r.stdout)

    def test_fail_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=False)
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            r = subprocess.run(
                [str(self._script_path()), "--no-host"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            td.cleanup()
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("gateway health: FAIL", r.stdout)
            self.assertIn("NEXT:", r.stdout)

    def test_missing_openclaw_exit_2(self):
        env = dict(os.environ)
        # Force a PATH that typically excludes user-installed `openclaw` (often in ~/.npm-global/bin).
        env["PATH"] = "/usr/bin:/bin"
        # Ensure the script doesn't fall back to the repo wrapper, which can locate
        # ~/.npm-global/bin/openclaw even when PATH is minimal.
        env["OPENCLAW_BIN"] = "openclaw"
        env["STRATUS_SKIP_HOST"] = "1"
        r = subprocess.run(
            [str(self._script_path()), "--no-host"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("openclaw: MISSING", r.stdout)
