import os
import stat
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


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
      if [[ "${{2-}}" == "--json" ]]; then
        cat <<'JSON'
{{"service":{{"loaded":true,"runtime":{{"status":"running"}},"configAudit":{{"ok":true}}}},"rpc":{{"ok":true}}}}
JSON
        exit 0
      fi
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

    def _start_http_server(self, *, readyz: int = 200, healthz: int = 200):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                status = 404
                if self.path == "/readyz":
                    status = readyz
                elif self.path == "/healthz":
                    status = healthz
                self.send_response(status)
                self.end_headers()
                self.wfile.write(f"{status}\n".encode("utf-8"))

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_address[1]}"

    def _write_logs(self, root: Path, *, gateway_lines: list[str] | None = None, err_lines: list[str] | None = None) -> tuple[Path, Path]:
        gateway_log = root / "gateway.log"
        gateway_err = root / "gateway.err.log"
        gateway_log.write_text("\n".join(gateway_lines or []) + ("\n" if gateway_lines else ""), encoding="utf-8")
        gateway_err.write_text("\n".join(err_lines or []) + ("\n" if err_lines else ""), encoding="utf-8")
        return gateway_log, gateway_err

    def test_ok_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=True)
            gateway_log, gateway_err = self._write_logs(Path(td.name))
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
            env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
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
            self.assertIn("gateway overall: OK", r.stdout)

    def test_fail_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=False)
            gateway_log, gateway_err = self._write_logs(Path(td.name))
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
            env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
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

    def test_gateway_degraded_when_rpc_or_config_audit_is_not_clean(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            p = Path(td.name) / "openclaw"
            p.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
cmd="${1-}"
shift || true
case "$cmd" in
  health)
    exit 0
    ;;
  gateway)
    sub="${1-}"
    if [[ "$sub" == "status" && "${2-}" == "--json" ]]; then
      cat <<'JSON'
{"service":{"loaded":true,"runtime":{"status":"running"},"configAudit":{"ok":false}},"rpc":{"ok":true}}
JSON
      exit 0
    fi
    if [[ "$sub" == "status" ]]; then
      exit 0
    fi
    ;;
esac
exit 2
""",
                encoding="utf-8",
            )
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            gateway_log, gateway_err = self._write_logs(Path(td.name))
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
            env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
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
            self.assertIn("gateway config audit: DEGRADED", r.stdout)
            self.assertIn("gateway overall: DEGRADED", r.stdout)

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

    def test_app_server_probes_pass_when_readyz_and_healthz_ok(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=True)
            gateway_log, gateway_err = self._write_logs(Path(td.name))
            server, base_url = self._start_http_server()
            try:
                env = dict(os.environ)
                env["PATH"] = f"{td.name}:{env.get('PATH','')}"
                env["STRATUS_SKIP_HOST"] = "1"
                env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
                env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
                r = subprocess.run(
                    [str(self._script_path()), "--no-host", "--app-server", base_url],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                td.cleanup()

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("codex app-server readyz: OK", r.stdout)
            self.assertIn("codex app-server healthz: OK", r.stdout)

    def test_app_server_probe_failure_turns_check_red(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=True)
            gateway_log, gateway_err = self._write_logs(Path(td.name))
            server, base_url = self._start_http_server(readyz=503, healthz=200)
            try:
                env = dict(os.environ)
                env["PATH"] = f"{td.name}:{env.get('PATH','')}"
                env["STRATUS_SKIP_HOST"] = "1"
                env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
                env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
                r = subprocess.run(
                    [str(self._script_path()), "--no-host", f"--app-server={base_url}"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                td.cleanup()

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("codex app-server readyz: FAIL", r.stdout)
            self.assertIn("Check the Codex app-server listener", r.stdout)

    def test_recent_channel_stability_signals_degrade_healthcheck(self):
        with tempfile.TemporaryDirectory() as d:
            td = tempfile.TemporaryDirectory(dir=d)
            self._write_fake_openclaw(td, health_ok=True)
            gateway_log, gateway_err = self._write_logs(
                Path(td.name),
                gateway_lines=[
                    "2026-03-31T21:40:42.159-04:00 [discord] [default] auto-restart attempt 1/10 in 5s",
                ],
                err_lines=[
                    "2026-03-31T21:40:53.645-04:00 [telegram] fetch fallback: enabling sticky IPv4-only dispatcher (codes=ETIMEDOUT,EHOSTUNREACH)",
                ],
            )
            env = dict(os.environ)
            env["PATH"] = f"{td.name}:{env.get('PATH','')}"
            env["STRATUS_SKIP_HOST"] = "1"
            env["OPENCLAW_GATEWAY_LOG"] = str(gateway_log)
            env["OPENCLAW_GATEWAY_ERR_LOG"] = str(gateway_err)
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
            self.assertIn("discord restart indicators: 1", r.stdout)
            self.assertIn("telegram ipv4 fallback indicators: 1", r.stdout)
            self.assertIn("Build an ORION incident bundle", r.stdout)
