from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "openclaw_operator_health_bundle.py"
    spec = importlib.util.spec_from_file_location("openclaw_operator_health_bundle", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOpenClawOperatorHealthBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_build_report_runs_standard_operator_checks(self):
        responses = [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "service": {
                            "loaded": True,
                            "runtime": {"status": "running"},
                            "configAudit": {"ok": True},
                        },
                        "rpc": {"ok": True},
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "defaultModel": "openai/gpt-5.4",
                        "auth": {
                            "probes": {
                                "results": [
                                    {"model": "google/gemini-2.5-flash-lite", "status": "ok"},
                                    {"model": "openai/gpt-5.4", "status": "ok"},
                                ]
                            }
                        },
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [
                        {
                            "audit": {"exists": True, "entryCount": 3},
                            "status": {"dirty": False},
                        }
                    ]
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "rem": {"sourceEntryCount": 3},
                        "deep": {"candidateCount": 3},
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "result": {
                            "payloads": [{"text": "operator-health-bundle-ok"}],
                            "meta": {
                                "agentMeta": {
                                    "provider": "openai",
                                    "model": "gpt-5.4",
                                    "sessionId": "abc123",
                                }
                            },
                        }
                    }
                ),
                stderr="",
            ),
        ]

        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses) as run_mock:
            report = self.mod.build_report(
                repo_root=Path("/repo"),
                agent="main",
                probe_max_tokens=16,
                smoke_message=self.mod.SMOKE_MESSAGE,
                smoke_thinking="low",
                smoke_timeout_s=120,
            )

        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(
            commands,
            [
                ["openclaw", "gateway", "status", "--json"],
                ["openclaw", "models", "status", "--probe", "--probe-max-tokens", "16", "--json"],
                ["openclaw", "memory", "status", "--agent", "main", "--json"],
                ["openclaw", "memory", "rem-harness", "--agent", "main", "--json"],
                [
                    "openclaw",
                    "agent",
                    "--agent",
                    "main",
                    "--message",
                    self.mod.SMOKE_MESSAGE,
                    "--thinking",
                    "low",
                    "--timeout",
                    "120",
                    "--json",
                ],
            ],
        )
        self.assertTrue(report["summary"]["overall_ok"])
        self.assertEqual(report["summary"]["failed_checks"], [])
        self.assertTrue(report["summary"]["gateway_ok"])
        self.assertTrue(report["summary"]["models_ok"])
        self.assertTrue(report["summary"]["memory_ok"])
        self.assertTrue(report["summary"]["rem_harness_ok"])
        self.assertTrue(report["summary"]["smoke_ok"])

    def test_main_writes_bundle_artifacts(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='{"service":{"loaded":true,"runtime":{"status":"running"},"configAudit":{"ok":true}},"rpc":{"ok":true}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"defaultModel":"openai/gpt-5.4","auth":{"probes":{"results":[{"model":"openai/gpt-5.4","status":"ok"}]}}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='[{"audit":{"exists":true,"entryCount":1},"status":{"dirty":false}}]', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"rem":{"sourceEntryCount":1},"deep":{"candidateCount":1}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"result":{"payloads":[{"text":"operator-health-bundle-ok"}],"meta":{"agentMeta":{"provider":"openai","model":"gpt-5.4"}}}}', stderr=""),
        ]

        with tempfile.TemporaryDirectory() as td:
            out_json = Path(td) / "bundle.json"
            out_md = Path(td) / "bundle.md"
            with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
                sys,
                "argv",
                [
                    "openclaw_operator_health_bundle.py",
                    "--repo-root",
                    "/repo",
                    "--output-json",
                    str(out_json),
                    "--output-md",
                    str(out_md),
                    "--json",
                ],
            ):
                rc = self.mod.main()

            self.assertEqual(rc, 0)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertTrue(data["summary"]["overall_ok"])
            self.assertIn("OpenClaw Operator Health Bundle", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
