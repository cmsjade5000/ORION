import os
import stat
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


class TestResurrectOrionMac(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _script_path(self) -> Path:
        return self._repo_root() / "scripts" / "resurrect_orion_mac.sh"

    def _start_http_server(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path in {"/readyz", "/healthz"}:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok\n")
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, f"http://127.0.0.1:{server.server_address[1]}"

    def _write_fake_openclaw(self, root: Path, *, fail_until_restart: bool, log_path: Path) -> Path:
        state_path = root / "state.txt"
        script = root / "fake-openclaw.sh"
        body = f"""#!/usr/bin/env bash
set -euo pipefail
state_file={state_path!s}
log_file={log_path!s}
cmd="${{1-}}"
shift || true
state="fresh"
if [[ -f "$state_file" ]]; then
  state="$(cat "$state_file")"
fi
case "$cmd" in
  gateway)
    sub="${{1-}}"
    shift || true
    case "$sub" in
      status)
        if [[ "${{1-}}" == "--json" ]]; then
          if [[ "{'1' if fail_until_restart else '0'}" == "1" && "$state" != "restarted" ]]; then
            cat <<'JSON'
{{"service":{{"loaded":false,"runtime":{{"status":"stopped"}},"configAudit":{{"ok":true}}}},"rpc":{{"ok":false}}}}
JSON
          else
            cat <<'JSON'
{{"service":{{"loaded":true,"runtime":{{"status":"running"}},"configAudit":{{"ok":true}}}},"rpc":{{"ok":true}}}}
JSON
          fi
          exit 0
        fi
        echo "status"
        exit 0
        ;;
      restart)
        echo restarted > "$state_file"
        echo restart >> "$log_file"
        exit 0
        ;;
      install|start)
        echo "$sub" >> "$log_file"
        echo restarted > "$state_file"
        exit 0
        ;;
    esac
    ;;
  doctor)
    echo doctor >> "$log_file"
    exit 0
    ;;
esac
echo "unexpected command: $cmd $*" >&2
exit 2
"""
        script.write_text(body, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return script

    def test_healthy_gateway_skips_restart(self):
        with tempfile.TemporaryDirectory() as td_name:
            td = Path(td_name)
            actions = td / "actions.log"
            fake = self._write_fake_openclaw(td, fail_until_restart=False, log_path=actions)
            server, base_url = self._start_http_server()
            try:
                env = dict(os.environ)
                env["OPENCLAW_BIN"] = str(fake)
                env["ORION_GATEWAY_BASE_URL"] = base_url
                env["ORION_GATEWAY_GUARD_STATE_DIR"] = str(td / "state")
                env["ORION_GATEWAY_SETTLE_SECONDS"] = "0"
                result = subprocess.run(
                    [str(self._script_path())],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("no action needed", result.stdout.lower())
            self.assertFalse(actions.exists(), actions.read_text(encoding="utf-8") if actions.exists() else "")

    def test_failed_gateway_restarts_and_recovers(self):
        with tempfile.TemporaryDirectory() as td_name:
            td = Path(td_name)
            actions = td / "actions.log"
            fake = self._write_fake_openclaw(td, fail_until_restart=True, log_path=actions)
            server, base_url = self._start_http_server()
            try:
                env = dict(os.environ)
                env["OPENCLAW_BIN"] = str(fake)
                env["ORION_GATEWAY_BASE_URL"] = base_url
                env["ORION_GATEWAY_GUARD_STATE_DIR"] = str(td / "state")
                env["ORION_GATEWAY_SETTLE_SECONDS"] = "0"
                result = subprocess.run(
                    [str(self._script_path())],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("restarting openclaw gateway", result.stdout.lower())
            self.assertIn("gateway recovery complete", result.stdout.lower())
            self.assertEqual(actions.read_text(encoding="utf-8").strip(), "restart")

    def test_restart_guard_blocks_flapping(self):
        with tempfile.TemporaryDirectory() as td_name:
            td = Path(td_name)
            actions = td / "actions.log"
            fake = self._write_fake_openclaw(td, fail_until_restart=True, log_path=actions)
            state_dir = td / "state"
            state_dir.mkdir()
            now = int(subprocess.check_output(["date", "+%s"], text=True).strip())
            (state_dir / "restart-epochs.log").write_text(f"{now}\n{now}\n", encoding="utf-8")
            env = dict(os.environ)
            env["OPENCLAW_BIN"] = str(fake)
            env["ORION_GATEWAY_BASE_URL"] = "http://127.0.0.1:1"
            env["ORION_GATEWAY_GUARD_STATE_DIR"] = str(state_dir)
            env["ORION_GATEWAY_SETTLE_SECONDS"] = "0"
            result = subprocess.run(
                [str(self._script_path())],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("restart guard active", result.stdout.lower())
            self.assertFalse(actions.exists(), actions.read_text(encoding="utf-8") if actions.exists() else "")


if __name__ == "__main__":
    unittest.main()
