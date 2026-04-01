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


def _load_bundle_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "orion_incident_bundle.py"
    assert script_path.exists(), f"Missing script: {script_path}"
    spec = importlib.util.spec_from_file_location("orion_incident_bundle", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOrionIncidentBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = _load_bundle_module()

    def _write_logs(self, log_dir: Path, *, include_err: bool = True) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "gateway.log").write_text("gateway boot ok\nall clear\n", encoding="utf-8")
        if include_err:
            (log_dir / "gateway.err.log").write_text("no errors\n", encoding="utf-8")

    def _fake_run_factory(self, responses: dict[tuple[str, ...], object]):
        def fake_run(argv, cwd=None, stdout=None, stderr=None, text=None, check=None, timeout=None):
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

        return fake_run

    def _run_bundle(self, root: Path, log_dir: Path, responses: dict[tuple[str, ...], object], *, write_latest: bool = True):
        argv = [
            "orion_incident_bundle.py",
            "--repo-root",
            str(root),
            "--log-dir",
            str(log_dir),
            "--json",
        ]
        if write_latest:
            argv.append("--write-latest")

        fake_run = self._fake_run_factory(responses)
        stdout = io.StringIO()
        with mock.patch.object(self.bundle.subprocess, "run", side_effect=fake_run):
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(stdout):
                    rc = self.bundle.main()
        payload = json.loads(stdout.getvalue())
        return rc, payload

    def test_success_path_writes_bundle_and_latest_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log_dir = root / "logs"
            self._write_logs(log_dir)

            responses = {
                ("openclaw", "gateway", "health"): {
                    "returncode": 0,
                    "stdout": "gateway health: OK\n",
                    "stderr": "",
                },
                ("openclaw", "gateway", "status", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "service": {
                                "loaded": True,
                                "runtime": {"status": "running"},
                                "configAudit": {"ok": True},
                            },
                            "rpc": {"ok": True},
                        }
                    ),
                    "stderr": "",
                },
                ("openclaw", "channels", "status", "--probe", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "channels": {
                                "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                                "discord": {"configured": True, "running": True, "probe": {"ok": True}},
                                "slack": {"configured": True, "running": False, "lastError": "disabled"},
                            }
                        }
                    ),
                    "stderr": "",
                },
                ("openclaw", "doctor", "--non-interactive"): {
                    "returncode": 0,
                    "stdout": "doctor ok\n",
                    "stderr": "",
                },
                ("openclaw", "tasks", "list", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps([{"id": "task-1"}, {"id": "task-2"}]),
                    "stderr": "",
                },
                ("openclaw", "tasks", "audit", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps({"warnings": [{"id": "warn-1"}]}),
                    "stderr": "",
                },
                ("codex", "--version"): {
                    "returncode": 0,
                    "stdout": "codex-cli 0.118.0\n",
                    "stderr": "",
                },
            }

            rc, payload = self._run_bundle(root, log_dir, responses)

            self.assertEqual(rc, 0)
            bundle_dir = Path(payload["bundle_dir"])
            self.assertTrue(bundle_dir.exists())
            self.assertIn(str(root / "tmp" / "incidents"), str(bundle_dir))
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["gateway"]["status_ok"])
            self.assertTrue(payload["channels"]["status_ok"])
            self.assertEqual(payload["tasks"]["list_count"], 2)
            self.assertEqual(payload["tasks"]["audit_count"], 1)
            self.assertEqual(payload["signals"]["discord_stale_socket_restarts"], 0)
            self.assertEqual(payload["signals"]["telegram_ipv4_fallbacks"], 0)
            self.assertEqual(payload["signals"]["stale_task_runs"], 0)
            self.assertEqual(payload["signals"]["exec_elevation_failures"], 0)
            self.assertTrue((bundle_dir / "summary.json").exists())
            self.assertTrue((bundle_dir / "summary.md").exists())
            self.assertTrue((root / "tmp" / "orion_incident_bundle_latest.json").exists())
            self.assertTrue((root / "tasks" / "NOTES" / "orion-ops-status.md").exists())
            self.assertTrue((bundle_dir / "gateway.log.tail.txt").exists())
            self.assertTrue((bundle_dir / "gateway.err.log.tail.txt").exists())
            self.assertTrue((bundle_dir / "commands" / "gateway.status.json").exists())
            self.assertTrue((bundle_dir / "commands" / "channels.status.json").exists())
            self.assertTrue((bundle_dir / "commands" / "tasks.audit.json").exists())

    def test_partial_failures_and_missing_logs_still_complete_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log_dir = root / "logs"
            self._write_logs(log_dir, include_err=False)
            (log_dir / "gateway.log").write_text(
                "approval timeout: no approval client was available\n",
                encoding="utf-8",
            )

            responses = {
                ("openclaw", "gateway", "health"): {
                    "returncode": 1,
                    "stdout": "gateway health: FAIL\n",
                    "stderr": "down\n",
                },
                ("openclaw", "gateway", "status", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "service": {
                                "loaded": True,
                                "runtime": {"status": "running"},
                                "configAudit": {"ok": False},
                            },
                            "rpc": {"ok": False},
                        }
                    ),
                    "stderr": "",
                },
                ("openclaw", "channels", "status", "--probe", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "channels": {
                                "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                                "discord": {
                                    "configured": True,
                                    "running": False,
                                    "lastError": "Unknown system error -11: read",
                                    "probe": {"ok": True},
                                },
                            }
                        }
                    ),
                    "stderr": "",
                },
                ("openclaw", "doctor", "--non-interactive"): {
                    "returncode": 0,
                    "stdout": "doctor ok\n",
                    "stderr": "",
                },
                ("openclaw", "tasks", "list", "--json"): {
                    "returncode": 0,
                    "stdout": json.dumps([{"id": "task-1"}]),
                    "stderr": "",
                },
                ("openclaw", "tasks", "audit", "--json"): {
                    "returncode": 2,
                    "stdout": json.dumps({"findings": [{"id": "audit-1", "code": "stale_running"}]}),
                    "stderr": "audit failed\n",
                },
                ("codex", "--version"): FileNotFoundError("codex"),
            }

            rc, payload = self._run_bundle(root, log_dir, responses, write_latest=False)

            self.assertEqual(rc, 0)
            bundle_dir = Path(payload["bundle_dir"])
            self.assertTrue(bundle_dir.exists())
            self.assertEqual(payload["status"], "degraded")
            self.assertFalse(payload["gateway"]["status_ok"])
            self.assertFalse(payload["channels"]["status_ok"])
            self.assertFalse(payload["tasks"]["audit_ok"])
            self.assertEqual(payload["tasks"]["audit_count"], 1)
            self.assertEqual(payload["signals"]["approval_timeouts"], 1)
            self.assertEqual(payload["signals"]["stale_task_runs"], 1)
            self.assertEqual(payload["codex_ready"], False)

            summary = json.loads((bundle_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "degraded")
            self.assertEqual(summary["commands"][-1]["note"], "missing-command")
            self.assertTrue((bundle_dir / "gateway.err.log.tail.txt").exists())
            self.assertEqual((bundle_dir / "gateway.err.log.tail.txt").read_text(encoding="utf-8"), "")

    def test_bundle_parses_json_from_stderr_when_stdout_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log_dir = root / "logs"
            self._write_logs(log_dir)

            task_list = json.dumps({"count": 3, "tasks": [{"id": "a"}, {"id": "b"}, {"id": "c"}]})
            task_audit = json.dumps({"summary": {"warnings": 2, "errors": 1}, "findings": [{"id": "warn-1"}]})

            responses = {
                ("openclaw", "gateway", "health"): {
                    "returncode": 0,
                    "stdout": "gateway health: OK\n",
                    "stderr": "",
                },
                ("openclaw", "gateway", "status", "--json"): {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": json.dumps(
                        {
                            "service": {
                                "loaded": True,
                                "runtime": {"status": "running"},
                                "configAudit": {"ok": True},
                            },
                            "rpc": {"ok": True},
                        }
                    ),
                },
                ("openclaw", "channels", "status", "--probe", "--json"): {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": json.dumps(
                        {
                            "channels": {
                                "telegram": {"configured": True, "running": True, "probe": {"ok": True}},
                                "discord": {"configured": True, "running": True, "probe": {"ok": True}},
                            }
                        }
                    ),
                },
                ("openclaw", "doctor", "--non-interactive"): {
                    "returncode": 0,
                    "stdout": "doctor ok\n",
                    "stderr": "",
                },
                ("openclaw", "tasks", "list", "--json"): {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": task_list,
                },
                ("openclaw", "tasks", "audit", "--json"): {
                    "returncode": 0,
                    "stdout": "",
                    "stderr": task_audit,
                },
                ("codex", "--version"): {
                    "returncode": 0,
                    "stdout": "codex-cli 0.118.0\n",
                    "stderr": "",
                },
            }

            rc, payload = self._run_bundle(root, log_dir, responses)

            self.assertEqual(rc, 0)
            self.assertEqual(payload["tasks"]["list_count"], 3)
            self.assertEqual(payload["tasks"]["audit_count"], 1)
            self.assertTrue(payload["gateway"]["status_ok"])


if __name__ == "__main__":
    unittest.main()
