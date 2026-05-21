import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_status_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "orion_machine_status.py"
    assert script_path.exists(), f"Missing script: {script_path}"
    spec = importlib.util.spec_from_file_location("orion_machine_status", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOrionMachineStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status = _load_status_module()

    def _run_status(self, root: Path, responses: dict[tuple[str, ...], object], extra_args: list[str] | None = None):
        argv = [
            "orion_machine_status.py",
            "--repo-root",
            str(root),
            "--json",
        ]
        if extra_args:
            argv.extend(extra_args)

        def fake_run(argv, cwd=None, stdout=None, stderr=None, stdin=None, text=None, check=None, timeout=None, **_kwargs):
            key = tuple(argv)
            value = responses.get(key)
            if value is None:
                raise AssertionError(f"Unexpected command: {argv}")
            if isinstance(value, Exception):
                raise value
            return SimpleNamespace(
                returncode=value["returncode"],
                stdout=value.get("stdout", ""),
                stderr=value.get("stderr", ""),
            )

        stdout = io.StringIO()
        with mock.patch.object(self.status.subprocess, "run", side_effect=fake_run):
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(stdout):
                    rc = self.status.main()
        return rc, json.loads(stdout.getvalue())

    def test_digest_returns_stable_top_level_keys(self):
        with tempfile.TemporaryDirectory() as td_name:
            root = Path(td_name)
            logs = root / "logs"
            logs.mkdir()
            (logs / "orion_resurrector.log").write_text(
                "[2026-05-21 10:00:00] Pre-check: classification=degraded loaded=0 runtime=unknown rpc=unknown port=1 readyz=1 healthz=1\n"
                "[2026-05-21 10:00:00] Gateway degraded but still serving local probes; skipping automatic restart\n",
                encoding="utf-8",
            )
            latest = root / "tmp" / "openclaw_operator_health_bundle_latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text(json.dumps({"status": "ok", "gateway": {"runtime_status": "running"}}), encoding="utf-8")
            launch_agents = root / "LaunchAgents"
            launch_agents.mkdir()
            (launch_agents / "com.openclaw.orion.resurrector.plist").write_text(
                "<plist><dict><key>ProgramArguments</key><array>"
                f"<string>{root}/scripts/resurrect_orion_mac.sh</string>"
                "</array></dict></plist>",
                encoding="utf-8",
            )
            storage_watch = root / "storage-watch.sh"
            storage_watch.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            responses = {
                ("launchctl", "list"): {
                    "returncode": 0,
                    "stdout": "123\t0\tcom.openclaw.orion.resurrector\n-\t78\tcom.remodex.bridge\n",
                },
                ("/bin/zsh", "-lc", "command -v codex"): {"returncode": 0, "stdout": "/tmp/bin/codex\n"},
                ("codex", "--version"): {"returncode": 0, "stdout": "codex-cli 0.131.0\n"},
                ("/bin/zsh", "-lc", "command -v openclaw"): {"returncode": 0, "stdout": "/tmp/bin/openclaw\n"},
                ("openclaw", "--version"): {"returncode": 0, "stdout": "OpenClaw 2026.5.12\n"},
                (str(storage_watch),): {"returncode": 0, "stdout": "Data OK 120Gi free\nhome .git ALERT 47.2G\n"},
                ("remodex", "status"): {"returncode": 0, "stdout": "Bridge: running\nConnection: connected\n"},
            }

            rc, payload = self._run_status(
                root,
                responses,
                [
                    "--logs-dir",
                    str(logs),
                    "--launch-agents-dir",
                    str(launch_agents),
                    "--storage-watch",
                    str(storage_watch),
                ],
            )

            self.assertEqual(rc, 0)
            self.assertEqual(
                set(payload),
                {
                    "generated_at",
                    "repo_root",
                    "status",
                    "warnings",
                    "gateway_guard",
                    "operator_health_bundle",
                    "launchagents",
                    "binaries",
                    "storage",
                    "remodex",
                },
            )
            self.assertEqual(payload["gateway_guard"]["last_classification"], "degraded")
            self.assertEqual(payload["operator_health_bundle"]["status"], "ok")
            self.assertEqual(payload["binaries"]["codex"]["version"], "codex-cli 0.131.0")
            self.assertEqual(payload["binaries"]["openclaw"]["version"], "OpenClaw 2026.5.12")
            self.assertEqual(payload["storage"]["headline"], "Data OK 120Gi free")
            self.assertEqual(payload["remodex"]["status"], "ok")
            self.assertEqual(payload["status"], "warn")
            self.assertTrue(any("com.remodex.bridge" in warning for warning in payload["warnings"]))

    def test_missing_optional_tools_degrade_to_unknown(self):
        with tempfile.TemporaryDirectory() as td_name:
            root = Path(td_name)
            logs = root / "logs"
            logs.mkdir()
            launch_agents = root / "LaunchAgents"
            launch_agents.mkdir()
            responses = {
                ("launchctl", "list"): FileNotFoundError("launchctl missing"),
                ("/bin/zsh", "-lc", "command -v codex"): {"returncode": 1, "stdout": ""},
                ("codex", "--version"): FileNotFoundError("codex missing"),
                ("/bin/zsh", "-lc", "command -v openclaw"): {"returncode": 1, "stdout": ""},
                ("openclaw", "--version"): FileNotFoundError("openclaw missing"),
                ("remodex", "status"): FileNotFoundError("remodex missing"),
            }

            rc, payload = self._run_status(
                root,
                responses,
                [
                    "--logs-dir",
                    str(logs),
                    "--launch-agents-dir",
                    str(launch_agents),
                    "--storage-watch",
                    str(root / "missing-storage-watch.sh"),
                ],
            )

            self.assertEqual(rc, 0)
            self.assertEqual(payload["status"], "warn")
            self.assertEqual(payload["gateway_guard"]["status"], "unknown")
            self.assertEqual(payload["operator_health_bundle"]["status"], "unknown")
            self.assertEqual(payload["binaries"]["codex"]["path"], None)
            self.assertEqual(payload["binaries"]["openclaw"]["version"], None)
            self.assertEqual(payload["storage"]["status"], "unknown")
            self.assertEqual(payload["remodex"]["status"], "unknown")
            self.assertGreaterEqual(len(payload["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
