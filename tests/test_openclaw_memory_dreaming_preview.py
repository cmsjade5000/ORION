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
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":true}}]', stderr=""),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "deepConfig": {"minScore": 0.8, "minRecallCount": 3, "minUniqueQueries": 3},
                        "deep": {
                            "candidateCount": 1,
                            "candidates": [
                                {
                                    "key": "memory:memory/2026-04-08.md:1:10",
                                    "path": "memory/2026-04-08.md",
                                    "score": 0.42,
                                    "recallCount": 1,
                                    "uniqueQueries": 1,
                                }
                            ],
                        },
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="candidate-a\ncandidate-b\n", stderr=""),
        ]

        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses) as run_mock:
            with mock.patch.object(
                self.mod,
                "_short_term_recall_summary",
                return_value={
                    "path": "/tmp/recall.json",
                    "exists": True,
                    "size_bytes": 12,
                    "entry_count": 4,
                    "updated_at": "2026-04-06T15:31:57.432Z",
                },
            ), mock.patch.object(
                self.mod,
                "_canonical_memory_summary",
                return_value={
                    "file_count": 3,
                    "newest_path": "/tmp/memory/2026-04-08.md",
                    "newest_mtime": "2026-04-08T21:50:00Z",
                },
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
        self.assertEqual(report["summary"]["candidate_count"], 1)
        self.assertEqual(report["summary"]["blocker_keys"], ["score", "recallCount", "uniqueQueries"])
        self.assertTrue(report["summary"]["canonical_memory_newer_than_recall"])
        self.assertEqual(report["summary"]["recommended_next_step"], "improve-memory-signal")

    def test_main_writes_optional_artifacts(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":false}}]', stderr=""),
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
                return_value={
                    "path": "/tmp/recall.json",
                    "exists": True,
                    "size_bytes": 24,
                    "entry_count": 2,
                    "updated_at": "2026-04-06T15:31:57.432Z",
                },
            ), mock.patch.object(
                self.mod,
                "_canonical_memory_summary",
                return_value={
                    "file_count": 2,
                    "newest_path": "/tmp/memory/2026-04-08.md",
                    "newest_mtime": "2026-04-08T21:50:00Z",
                },
            ):
                rc = self.mod.main()

            self.assertEqual(rc, 0)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(data["limit"], 5)
            self.assertEqual(data["summary"]["recommended_next_step"], "fix-memory-backend")
            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("OpenClaw Memory Dreaming Preview", markdown)
            self.assertIn("## Freshness", markdown)
            self.assertIn("## Promotion Blockers", markdown)

    def test_missing_recall_store_changes_recommendation(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":true}}]', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"candidates":[]}', stderr=""),
            SimpleNamespace(returncode=0, stdout="No short-term recall candidates.\n", stderr=""),
        ]
        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
            self.mod,
            "_short_term_recall_summary",
            return_value={"path": "/tmp/recall.json", "exists": False, "size_bytes": 0, "entry_count": 0, "updated_at": None},
        ), mock.patch.object(
            self.mod,
            "_canonical_memory_summary",
            return_value={"file_count": 0, "newest_path": None, "newest_mtime": None},
        ):
            report = self.mod.build_report(limit=3)

        self.assertFalse(report["summary"]["recall_store_exists"])
        self.assertEqual(report["summary"]["recall_entry_count"], 0)
        self.assertEqual(report["summary"]["recommended_next_step"], "build-recall-store")

    def test_build_report_surfaces_candidate_threshold_failures(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":true}}]', stderr=""),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "deepConfig": {"minScore": 0.8, "minRecallCount": 3, "minUniqueQueries": 3},
                        "deep": {
                            "candidateCount": 2,
                            "candidates": [
                                {
                                    "key": "memory:memory/2026-04-08.md:1:10",
                                    "path": "memory/2026-04-08.md",
                                    "score": 0.41,
                                    "recallCount": 1,
                                    "uniqueQueries": 1,
                                },
                                {
                                    "key": "memory:memory/2026-04-06.md:1:10",
                                    "path": "memory/2026-04-06.md",
                                    "score": 0.55,
                                    "recallCount": 2,
                                    "uniqueQueries": 1,
                                },
                            ],
                        },
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="No short-term recall candidates.\n", stderr=""),
        ]
        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
            self.mod,
            "_short_term_recall_summary",
            return_value={
                "path": "/tmp/recall.json",
                "exists": True,
                "size_bytes": 24,
                "entry_count": 2,
                "updated_at": "2026-04-06T15:31:57.432Z",
            },
        ), mock.patch.object(
            self.mod,
            "_canonical_memory_summary",
            return_value={"file_count": 2, "newest_path": "/tmp/memory/2026-04-08.md", "newest_mtime": "2026-04-08T21:50:00Z"},
        ):
            report = self.mod.build_report(limit=5)

        self.assertEqual(report["summary"]["blocker_keys"], ["score", "recallCount", "uniqueQueries"])
        self.assertEqual(report["summary"]["recommended_next_step"], "improve-memory-signal")
        self.assertIn("score 0.41 < 0.80", report["promotion_blockers"]["top_failures"][0]["failures"])

    def test_build_report_marks_canonical_memory_newer_than_recall_store(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":true}}]', stderr=""),
            SimpleNamespace(returncode=0, stdout='{"deep":{"candidateCount":0,"candidates":[]}}', stderr=""),
            SimpleNamespace(returncode=0, stdout="No short-term recall candidates.\n", stderr=""),
        ]
        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
            self.mod,
            "_short_term_recall_summary",
            return_value={
                "path": "/tmp/recall.json",
                "exists": True,
                "size_bytes": 24,
                "entry_count": 2,
                "updated_at": "2026-04-06T15:31:57.432Z",
            },
        ), mock.patch.object(
            self.mod,
            "_canonical_memory_summary",
            return_value={"file_count": 2, "newest_path": "/tmp/memory/2026-04-08.md", "newest_mtime": "2026-04-08T21:50:00Z"},
        ):
            report = self.mod.build_report(limit=5)

        self.assertTrue(report["summary"]["canonical_memory_newer_than_recall"])

    def test_no_candidates_still_reports_blocker_summary(self):
        responses = [
            SimpleNamespace(returncode=0, stdout='[{"agentId":"main","embeddingProbe":{"ok":true}}]', stderr=""),
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "deepConfig": {"minScore": 0.8, "minRecallCount": 3, "minUniqueQueries": 3},
                        "deep": {
                            "candidateCount": 1,
                            "candidates": [
                                {
                                    "key": "memory:memory/2026-04-08.md:1:10",
                                    "path": "memory/2026-04-08.md",
                                    "score": 0.42,
                                    "recallCount": 1,
                                    "uniqueQueries": 1,
                                }
                            ],
                        },
                    }
                ),
                stderr="",
            ),
            SimpleNamespace(returncode=0, stdout="No short-term recall candidates.\n", stderr=""),
        ]
        with mock.patch.object(self.mod.subprocess, "run", side_effect=responses), mock.patch.object(
            self.mod,
            "_short_term_recall_summary",
            return_value={
                "path": "/tmp/recall.json",
                "exists": True,
                "size_bytes": 24,
                "entry_count": 2,
                "updated_at": "2026-04-06T15:31:57.432Z",
            },
        ), mock.patch.object(
            self.mod,
            "_canonical_memory_summary",
            return_value={"file_count": 2, "newest_path": "/tmp/memory/2026-04-08.md", "newest_mtime": "2026-04-08T21:50:00Z"},
        ):
            report = self.mod.build_report(limit=5)

        markdown = self.mod._render_markdown(report)
        self.assertIn("failure_keys", markdown)
        self.assertIn("memory/2026-04-08.md", markdown)
