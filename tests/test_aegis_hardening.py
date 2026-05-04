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
        self.assertIn("/etc/systemd/system/aegis-maintenance-orion.service", script)
        self.assertIn("/etc/systemd/system/aegis-openclaw-update.service", script)
        self.assertIn('cp "$current_tmp" "$drift_tmp"', script)
        self.assertIn("baseline unchanged pending review", script)
        self.assertIn('drift_fingerprint_file="$STATE_DIR/config_hashes.drift.fingerprint"', script)
        self.assertIn('drift_incident_file="$STATE_DIR/config_hashes.drift.incident"', script)
        self.assertIn('if [ "$current_fingerprint" != "$last_drift_fingerprint" ]; then', script)
        self.assertIn('"config_drift_${current_fingerprint}" 31536000', script)
        self.assertIn("config drift unchanged; suppressing repeat alert", script)
        self.assertIn('rm -f "$drift_tmp" "$drift_fingerprint_file" "$drift_incident_file"', script)
        drift_section = script.split('if ! cmp -s "$hash_file" "$current_tmp"; then', 1)[1]
        drift_section = drift_section.split("\nfi\n\n# 5) Tailscale peer changes", 1)[0]
        self.assertNotIn('cp "$current_tmp" "$hash_file"', drift_section)

    def test_monitor_debounces_orion_health_before_restart_or_notify(self):
        script = (self._repo_root() / "scripts" / "aegis_remote" / "aegis-monitor-orion").read_text(
            encoding="utf-8"
        )
        self.assertIn("AEGIS_ORION_CONFIRM_FAILURE_SEC:=180", script)
        self.assertIn('outage_first_seen_file="$STATE_DIR/orion_outage_first_seen_epoch"', script)
        self.assertIn("SUSPECT: ORION health failed but not confirmed yet", script)
        self.assertIn('exit 0', script.split("SUSPECT: ORION health failed but not confirmed yet", 1)[1])
        self.assertIn("wait_for_health_after_restart", script)
        self.assertIn("AEGIS_ORION_POST_RESTART_WAIT_SEC:=180", script)
        self.assertIn("transient ORION health failure self-corrected before external alert", script)

    def test_sentinel_debounces_aegis_service_down_before_telegram_page(self):
        script = (self._repo_root() / "scripts" / "aegis_remote" / "aegis-sentinel").read_text(
            encoding="utf-8"
        )
        self.assertIn("AEGIS_OPENCLAW_DOWN_CONFIRM_SEC:=300", script)
        self.assertIn('OPENCLAW_DOWN_FIRST_SEEN_FILE="$STATE_DIR/openclaw_down_first_seen_epoch"', script)
        self.assertIn("wait_for_openclaw_service_active", script)
        self.assertIn("restarted quietly; suppressing Telegram page", script)
        self.assertIn("outage not confirmed yet", script)
        self.assertIn("has stayed down past the confirm window", script)
        service_section = script.split("# 1) OpenClaw service down", 1)[1]
        service_section = service_section.split("\n# 2) SSH auth anomalies", 1)[0]
        recovered_section = service_section.split("restarted quietly; suppressing Telegram page", 1)[1]
        recovered_section = recovered_section.split('elif [ "$elapsed" -lt "$AEGIS_OPENCLAW_DOWN_CONFIRM_SEC" ]; then', 1)[0]
        self.assertNotIn("alert_throttled", recovered_section)


if __name__ == "__main__":
    unittest.main()
