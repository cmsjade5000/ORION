import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestAegisHardening(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_aegis_defense_wrapper_quotes_remote_args_and_fails_closed_on_host_keys(self):
        script = self._repo_root() / "scripts" / "aegis_defense.sh"
        with tempfile.TemporaryDirectory() as td:
            bindir = Path(td) / "bin"
            bindir.mkdir(parents=True, exist_ok=True)
            fake_ssh = bindir / "ssh"
            log_path = Path(td) / "ssh_args.log"
            fake_ssh.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "${MOCK_SSH_LOG:?}"
""",
                encoding="utf-8",
            )
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)

            home = Path(td) / "home"
            (home / ".ssh").mkdir(parents=True, exist_ok=True)

            env = dict(os.environ)
            env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
            env["HOME"] = str(home)
            env["MOCK_SSH_LOG"] = str(log_path)

            proc = subprocess.run(
                ["bash", str(script), "show", "INC; touch /tmp/pwned"],
                cwd=str(self._repo_root()),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            args = log_path.read_text(encoding="utf-8").splitlines()
            self.assertIn("StrictHostKeyChecking=yes", args)
            self.assertIn(f"UserKnownHostsFile={home / '.ssh' / 'known_hosts'}", args)
            self.assertEqual(args[-2], "root@100.75.104.54")
            self.assertEqual(
                args[-1],
                r"exec /usr/local/bin/aegis-defend show INC\;\ touch\ /tmp/pwned",
            )

    def test_sentinel_tracks_env_file_and_preserves_baseline_on_drift(self):
        script = (self._repo_root() / "scripts" / "aegis_remote" / "aegis-sentinel").read_text(
            encoding="utf-8"
        )
        self.assertIn("/etc/aegis-monitor.env", script)
        self.assertIn('cp "$current_tmp" "$drift_tmp"', script)
        self.assertIn("baseline unchanged pending review", script)
        drift_section = script.split('if ! cmp -s "$hash_file" "$current_tmp"; then', 1)[1]
        drift_section = drift_section.split("\nfi\n\n# 5) Tailscale peer changes", 1)[0]
        self.assertNotIn('cp "$current_tmp" "$hash_file"', drift_section)


if __name__ == "__main__":
    unittest.main()
