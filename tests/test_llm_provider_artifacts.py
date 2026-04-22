import json
import subprocess
import sys
from pathlib import Path
import unittest


class LlmProviderArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.registry = json.loads((cls.repo / "config" / "llm_provider_registry.json").read_text(encoding="utf-8"))
        cls.matrix = json.loads((cls.repo / "config" / "llm_task_routing_matrix.json").read_text(encoding="utf-8"))
        cls.benchmark = json.loads((cls.repo / "config" / "llm_provider_benchmark_report.template.json").read_text(encoding="utf-8"))

    def test_registry_includes_required_provider_lanes(self) -> None:
        provider_ids = {item["provider_id"] for item in self.registry["providers"]}
        required = {
            "openai-control-plane",
            "kimi-k2-5-nvidia-build",
            "local-bounded-runtime",
            "openrouter-auto-primary",
            "openrouter-hunter-alpha",
            "openrouter-free-bounded",
        }
        self.assertTrue(
            required.issubset(provider_ids),
            f"Missing provider lanes: {sorted(required - provider_ids)}",
        )

    def test_openrouter_lanes_are_explicit(self) -> None:
        by_id = {item["provider_id"]: item for item in self.registry["providers"]}
        auto_primary = by_id["openrouter-auto-primary"]
        hunter_alpha = by_id["openrouter-hunter-alpha"]
        free_bounded = by_id["openrouter-free-bounded"]

        def assert_openrouter_lane(provider: dict[str, object], model_signal: str) -> None:
            api_path = str(provider["api_path"]).lower()
            self.assertIn("openrouter", api_path)
            self.assertTrue("chat/completions" in api_path or "/v1" in api_path)
            model_text = " ".join(str(model) for model in provider.get("models", [])).lower()
            self.assertIn(model_signal, model_text)

        assert_openrouter_lane(auto_primary, "auto")
        assert_openrouter_lane(hunter_alpha, "hunter")
        assert_openrouter_lane(free_bounded, "free")

    def test_openai_and_kimi_lanes_are_explicit(self) -> None:
        by_id = {item["provider_id"]: item for item in self.registry["providers"]}
        openrouter_auto = by_id["openrouter-auto-primary"]
        openai = by_id["openai-control-plane"]
        kimi = by_id["kimi-k2-5-nvidia-build"]
        self.assertEqual(openrouter_auto["lane"], "default-orchestrator")
        self.assertIn("routing", openrouter_auto["allowed_tasks"])
        self.assertEqual(openai["api_path"], "https://api.openai.com/v1/responses")
        self.assertEqual(openai["lane"], "premium-opt-in")
        self.assertIn("routing", openai["allowed_tasks"])
        self.assertIn("structured_outputs", openai["allowed_tasks"])
        self.assertEqual(kimi["models"], ["moonshotai/kimi-k2.5"])
        self.assertIn("research_synthesis", kimi["allowed_tasks"])

    def test_local_lane_stays_bounded(self) -> None:
        local = next(item for item in self.registry["providers"] if item["provider_id"] == "local-bounded-runtime")
        self.assertIn("summarization", local["allowed_tasks"])
        self.assertIn("specialist_orchestration", local["forbidden_tasks"])
        self.assertFalse(local["requires_hitl"])

    def test_routing_matrix_references_known_providers(self) -> None:
        provider_ids = {item["provider_id"] for item in self.registry["providers"]}
        for task in self.matrix["tasks"]:
            self.assertIn(task["primary_provider"], provider_ids)
            for provider_id in task["fallback_providers"]:
                self.assertIn(provider_id, provider_ids)
        by_task = {item["task_id"]: item for item in self.matrix["tasks"]}
        self.assertEqual(by_task["routing_and_handoffs"]["primary_provider"], "openrouter-auto-primary")
        self.assertEqual(by_task["bounded_local_utility"]["primary_provider"], "local-bounded-runtime")
        self.assertIn("openai-control-plane", by_task["routing_and_handoffs"]["fallback_providers"])

    def test_benchmark_template_tracks_expected_metrics(self) -> None:
        first = self.benchmark["results"][0]
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
        self.assertIn(self.benchmark["run_mode"], {"live", "dry_run"})
        self.assertIn("unready_providers", self.benchmark["summary"])
        self.assertEqual(self.benchmark["summary"]["primary_candidate"], "openrouter-auto-primary")

    def test_validator_script_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/validate_llm_provider_artifacts.py"],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("LLM_PROVIDER_ARTIFACTS_OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
