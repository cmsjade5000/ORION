#!/usr/bin/env python3
"""Validate ORION LLM provider artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "llm_provider_registry.json"
MATRIX = ROOT / "config" / "llm_task_routing_matrix.json"
BENCHMARK = ROOT / "config" / "llm_provider_benchmark_report.template.json"

EXPECTED_PROVIDER_IDS = {
    "openrouter-auto-primary",
    "openrouter-hunter-alpha",
    "openrouter-free-bounded",
    "gemini-openclaw",
    "openai-control-plane",
    "kimi-k2-5-nvidia-build",
    "local-bounded-runtime",
}
EXPECTED_TASK_IDS = {
    "routing_and_handoffs",
    "structured_output_validation",
    "research_and_second_opinions",
    "evals_and_trace_grading",
    "bounded_local_utility",
}
ALLOWED_PASS_FAIL = {"pass", "fail", "pending"}
REQUIRED_BENCHMARK_RESULT_KEYS = {
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
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_registry(errors: list[str]) -> dict[str, dict[str, object]]:
    data = load_json(REGISTRY)
    require(isinstance(data, dict), "registry must be a JSON object", errors)
    providers = data.get("providers") if isinstance(data, dict) else None
    require(isinstance(providers, list), "registry.providers must be a list", errors)
    provider_map: dict[str, dict[str, object]] = {}
    if not isinstance(providers, list):
        return provider_map

    for item in providers:
        require(isinstance(item, dict), "registry provider entries must be objects", errors)
        if not isinstance(item, dict):
            continue
        provider_id = item.get("provider_id")
        require(isinstance(provider_id, str) and provider_id, "provider_id must be a non-empty string", errors)
        if not isinstance(provider_id, str) or not provider_id:
            continue
        provider_map[provider_id] = item
        for key in (
            "display_name",
            "lane",
            "api_path",
            "api_surface",
            "role_summary",
        ):
            require(isinstance(item.get(key), str) and str(item.get(key)).strip(), f"{provider_id}: missing {key}", errors)
        for key in ("allowed_tasks", "forbidden_tasks", "models", "docs"):
            value = item.get(key)
            require(isinstance(value, list) and len(value) > 0, f"{provider_id}: {key} must be a non-empty list", errors)
        require(isinstance(item.get("fallback_order"), int), f"{provider_id}: fallback_order must be an int", errors)
        require(isinstance(item.get("requires_schema"), bool), f"{provider_id}: requires_schema must be a bool", errors)
        require(isinstance(item.get("requires_hitl"), bool), f"{provider_id}: requires_hitl must be a bool", errors)

    require(set(provider_map) == EXPECTED_PROVIDER_IDS, "registry provider ids do not match expected set", errors)
    return provider_map


def validate_matrix(provider_map: dict[str, dict[str, object]], errors: list[str]) -> None:
    data = load_json(MATRIX)
    require(isinstance(data, dict), "matrix must be a JSON object", errors)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    require(isinstance(tasks, list), "matrix.tasks must be a list", errors)
    seen: set[str] = set()
    if not isinstance(tasks, list):
        return

    for item in tasks:
        require(isinstance(item, dict), "matrix task entries must be objects", errors)
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        require(isinstance(task_id, str) and task_id, "task_id must be a non-empty string", errors)
        if not isinstance(task_id, str) or not task_id:
            continue
        seen.add(task_id)
        primary = item.get("primary_provider")
        require(primary in provider_map, f"{task_id}: unknown primary_provider {primary}", errors)
        fallbacks = item.get("fallback_providers")
        require(isinstance(fallbacks, list), f"{task_id}: fallback_providers must be a list", errors)
        if isinstance(fallbacks, list):
            for provider_id in fallbacks:
                require(provider_id in provider_map, f"{task_id}: unknown fallback provider {provider_id}", errors)
        require(isinstance(item.get("local_allowed"), bool), f"{task_id}: local_allowed must be bool", errors)
        require(isinstance(item.get("requires_schema"), bool), f"{task_id}: requires_schema must be bool", errors)
        require(isinstance(item.get("requires_hitl"), bool), f"{task_id}: requires_hitl must be bool", errors)

    require(seen == EXPECTED_TASK_IDS, "matrix task ids do not match expected set", errors)


def validate_benchmark(provider_map: dict[str, dict[str, object]], errors: list[str]) -> None:
    data = load_json(BENCHMARK)
    require(isinstance(data, dict), "benchmark template must be a JSON object", errors)
    summary = data.get("summary") if isinstance(data, dict) else None
    require(isinstance(summary, dict), "benchmark.summary must be an object", errors)
    if isinstance(summary, dict):
        require(summary.get("primary_candidate") in provider_map, "benchmark.primary_candidate must reference a provider", errors)
        require(isinstance(summary.get("promotion_recommended"), bool), "benchmark.promotion_recommended must be bool", errors)
        require(isinstance(summary.get("notes"), str), "benchmark.summary.notes must be str", errors)
        require(isinstance(summary.get("unready_providers"), list), "benchmark.summary.unready_providers must be list", errors)
    require(isinstance(data.get("run_mode"), str) and str(data.get("run_mode")).strip(), "benchmark.run_mode must be non-empty string", errors)
    results = data.get("results") if isinstance(data, dict) else None
    require(isinstance(results, list) and len(results) > 0, "benchmark.results must be a non-empty list", errors)
    if not isinstance(results, list):
        return
    for item in results:
        require(isinstance(item, dict), "benchmark result entries must be objects", errors)
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        require(provider in provider_map, f"benchmark result has unknown provider {provider}", errors)
        require(REQUIRED_BENCHMARK_RESULT_KEYS.issubset(item.keys()), f"benchmark {provider}: missing required result keys", errors)
        require(isinstance(item.get("scenario"), str) and str(item.get("scenario")).strip(), "benchmark scenario must be non-empty", errors)
        require(item.get("pass_fail") in ALLOWED_PASS_FAIL, "benchmark pass_fail must be pass|fail|pending", errors)
        require(isinstance(item.get("provider_ready"), bool), f"benchmark {provider}: provider_ready must be bool", errors)
        require(isinstance(item.get("request_surface"), str), f"benchmark {provider}: request_surface must be str", errors)
        require(isinstance(item.get("response_format_used"), str), f"benchmark {provider}: response_format_used must be str", errors)
        require(isinstance(item.get("schema_name"), str), f"benchmark {provider}: schema_name must be str", errors)
        require(isinstance(item.get("schema_enforced"), bool), f"benchmark {provider}: schema_enforced must be bool", errors)
        for key in ("model_requested", "model_used", "finish_reason", "error_code", "error_message", "skip_reason", "notes"):
            require(isinstance(item.get(key), str), f"benchmark {provider}: {key} must be str", errors)
        for key in ("http_status", "exit_code", "latency_ms", "cost_estimate", "tool_success_rate", "schema_failure_rate"):
            require(isinstance(item.get(key), (int, float)), f"benchmark {provider}: {key} must be numeric", errors)


def main() -> int:
    errors: list[str] = []
    provider_map = validate_registry(errors)
    validate_matrix(provider_map, errors)
    validate_benchmark(provider_map, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("LLM_PROVIDER_ARTIFACTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
