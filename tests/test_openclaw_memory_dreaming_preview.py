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
    script_path = repo_root / "scripts" / "openclaw_memory_dreaming_preview.py"
    spec = importlib.util.spec_from_file_location("openclaw_memory_dreaming_preview", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


class TestOpenClawMemoryDreamingPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_build_report_runs_expected_preview_commands(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='{"provider":{"ready":true}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"candidates":[]}', stderr=""),
            SimpleNamespace(returncode=0, stdout="candidate-a\ncandidate-b\n", stderr=""),
        ]

        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses) as run_mock:
            with mock.patch.object(
                self.mod,
                "_short_term_recall_summary",
                return_value={"path": "/tmp/recall.json", "exists": True, "size_bytes": 12, "entry_count": 4},
            ):
                report = self.mod.build_report(limit=7)

        commands = [call.args[0] for call in run_mock.call_args_list]
        self.assertEqual(
            commands,
            [
                ["openclaw", "memory", "status", "--deep", "--json"],
                ["openclaw", "memory", "rem-harness", "--json"],
                ["openclaw", "memory", "promote", "--limit", "7"],
            ],
        )
        self.assertTrue(report["summary"]["status_ok"])
        self.assertTrue(report["summary"]["rem_harness_ok"])
        self.assertTrue(report["summary"]["promote_preview_ok"])
        self.assertTrue(report["summary"]["provider_ready"])
        self.assertTrue(report["summary"]["recall_store_exists"])
        self.assertEqual(report["summary"]["recall_entry_count"], 4)
        self.assertEqual(report["summary"]["recommended_next_step"], "review-rem-harness")

    def test_main_writes_optional_artifacts(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='{"provider":{"ready":false}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"candidates":[{"kind":"deep"}]}', stderr=""),
            SimpleNamespace(returncode=0, stdout="candidate-a\n", stderr=""),
        ]
        with tempfile.TemporaryDirectory() as td:
            out_json = Path(td) / "preview.json"
            out_md = Path(td) / "preview.md"
            with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
                sys,
                "argv",
                [
                    "openclaw_memory_dreaming_preview.py",
                    "--limit",
                    "5",
                    "--output-json",
                    str(out_json),
                    "--output-md",
                    str(out_md),
                ],
            ), mock.patch.object(
                self.mod,
                "_short_term_recall_summary",
                return_value={"path": "/tmp/recall.json", "exists": True, "size_bytes": 24, "entry_count": 2},
            ):
                rc = self.mod.main()

            self.assertEqual(rc, 0)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(data["limit"], 5)
            self.assertEqual(data["summary"]["recommended_next_step"], "fix-memory-backend")
            self.assertIn("OpenClaw Memory Dreaming Preview", out_md.read_text(encoding="utf-8"))

    def test_missing_recall_store_changes_recommendation(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='{"provider":{"ready":true}}', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"candidates":[]}', stderr=""),
            SimpleNamespace(returncode=0, stdout="No short-term recall candidates.\n", stderr=""),
        ]
        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
            self.mod,
            "_short_term_recall_summary",
            return_value={"path": "/tmp/recall.json", "exists": False, "size_bytes": 0, "entry_count": 0},
        ):
            report = self.mod.build_report(limit=3)

        self.assertFalse(report["summary"]["recall_store_exists"])
        self.assertEqual(report["summary"]["recall_entry_count"], 0)
        self.assertEqual(report["summary"]["recommended_next_step"], "build-recall-store")
