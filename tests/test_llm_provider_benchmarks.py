import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LlmProviderBenchmarksTest(unittest.TestCase):
    def test_benchmark_script_dry_run_emits_report(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "run_llm_provider_benchmarks.py"
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "report.json"
            proc = subprocess.run(
                [sys.executable, str(script), "--dry-run", "--output-json", str(output), "--trace"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("results", payload)
            self.assertGreater(len(payload["results"]), 0)
            first = payload["results"][0]
            self.assertTrue(
                {
                    "provider",
                    "scenario",
                    "pass_fail",
                    "provider_ready",
                    "request_surface",
                    "response_format_used",
                    "schema_name",
                    "schema_enforced",
                    "model_requested",
                    "model_used",
                    "http_status",
                    "exit_code",
                    "finish_reason",
                    "error_code",
                    "error_message",
                    "skip_reason",
                    "latency_ms",
                    "cost_estimate",
                    "tool_success_rate",
                    "schema_failure_rate",
                    "notes",
                }.issubset(first)
            )
            self.assertEqual(payload["run_mode"], "dry_run")

    def test_readiness_check_reports_missing_openai_key(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "run_llm_provider_benchmarks.py"
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        proc = subprocess.run(
            [sys.executable, str(script), "--check-readiness", "--providers", "openai-control-plane"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["providers"][0]["provider"], "openai-control-plane")
        self.assertFalse(payload["providers"][0]["provider_ready"])
        self.assertIn("OPENAI_API_KEY", payload["providers"][0]["skip_reason"])

    def test_require_ready_fails_when_openai_key_missing(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "run_llm_provider_benchmarks.py"
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        proc = subprocess.run(
            [sys.executable, str(script), "--check-readiness", "--require-ready", "--providers", "openai-control-plane"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
