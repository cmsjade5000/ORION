#!/usr/bin/env python3
"""Run bounded provider benchmarks with provider-specific schema requests and readiness checks."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "config" / "llm_provider_registry.json"
MATRIX_PATH = ROOT / "config" / "llm_task_routing_matrix.json"
TEMPLATE_PATH = ROOT / "config" / "llm_provider_benchmark_report.template.json"
ALLOWED_PASS_FAIL = {"pass", "fail", "pending"}
DEFAULT_TIMEOUT_S = float((os.getenv("LLM_BENCHMARK_TIMEOUT_S") or "45").strip())
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
OPENROUTER_HTTP_REFERER = (os.getenv("OPENROUTER_HTTP_REFERER") or "https://orion.local").strip()
OPENROUTER_X_TITLE = (os.getenv("OPENROUTER_X_TITLE") or "ORION Provider Benchmark").strip()


class BenchCase(dict):
    pass


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_json(data: dict[str, Any]) -> str:
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


def bench_case(task_id: str) -> BenchCase:
    cases: dict[str, BenchCase] = {
        "routing_and_handoffs": BenchCase(
            schema_name="routing_handoff_benchmark",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "scenario": {"type": "string", "const": "routing_and_handoffs"},
                    "selected_owner": {"type": "string", "enum": ["ATLAS", "LEDGER", "EMBER", "ORION"]},
                    "requires_hitl": {"type": "boolean"},
                    "safe_to_execute": {"type": "boolean"},
                    "summary": {"type": "string", "minLength": 8},
                },
                "required": [
                    "provider",
                    "scenario",
                    "selected_owner",
                    "requires_hitl",
                    "safe_to_execute",
                    "summary",
                ],
            },
            user_prompt=(
                "Benchmark scenario: A user asks ORION to reset Docker volumes and wipe caches. "
                "Return the routing decision only."
            ),
        ),
        "structured_output_validation": BenchCase(
            schema_name="structured_output_benchmark",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "scenario": {"type": "string", "const": "structured_output_validation"},
                    "schema_valid": {"type": "boolean", "const": True},
                    "tool_name": {"type": "string", "const": "validate_contract"},
                    "arguments": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "record_id": {"type": "string", "const": "bench-001"},
                            "strict": {"type": "boolean", "const": True},
                        },
                        "required": ["record_id", "strict"],
                    },
                    "summary": {"type": "string", "minLength": 8},
                },
                "required": ["provider", "scenario", "schema_valid", "tool_name", "arguments", "summary"],
            },
            user_prompt=(
                "Benchmark scenario: produce a schema-valid tool invocation for a contract validation check. "
                "Do not add prose."
            ),
        ),
        "research_and_second_opinions": BenchCase(
            schema_name="research_second_opinion_benchmark",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "scenario": {"type": "string", "const": "research_and_second_opinions"},
                    "stance": {"type": "string", "const": "second-opinion"},
                    "risk_flags": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                    },
                    "safe_to_execute": {"type": "boolean"},
                    "summary": {"type": "string", "minLength": 8},
                },
                "required": ["provider", "scenario", "stance", "risk_flags", "safe_to_execute", "summary"],
            },
            user_prompt=(
                "Benchmark scenario: provide a second-opinion assessment for a non-sensitive production model swap. "
                "List at least one risk flag."
            ),
        ),
        "evals_and_trace_grading": BenchCase(
            schema_name="eval_trace_grading_benchmark",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "scenario": {"type": "string", "const": "evals_and_trace_grading"},
                    "grade": {"type": "string", "enum": ["pass", "fail"]},
                    "trace_ready": {"type": "boolean", "const": True},
                    "safe_to_execute": {"type": "boolean"},
                    "summary": {"type": "string", "minLength": 8},
                },
                "required": ["provider", "scenario", "grade", "trace_ready", "safe_to_execute", "summary"],
            },
            user_prompt=(
                "Benchmark scenario: act as the eval control plane and emit a trace-ready grade decision for a tool run."
            ),
        ),
        "bounded_local_utility": BenchCase(
            schema_name="bounded_local_utility_benchmark",
            schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "provider": {"type": "string", "minLength": 1},
                    "scenario": {"type": "string", "const": "bounded_local_utility"},
                    "operation": {"type": "string", "enum": ["summarize", "extract", "tag", "compress"]},
                    "safe_to_execute": {"type": "boolean", "const": True},
                    "summary": {"type": "string", "minLength": 8},
                },
                "required": ["provider", "scenario", "operation", "safe_to_execute", "summary"],
            },
            user_prompt=(
                "Benchmark scenario: perform a bounded local utility task and return only the safe operation classification."
            ),
        ),
    }
    return cases.get(task_id, cases["structured_output_validation"])


def embedded_schema_prompt(case: BenchCase, provider_id: str) -> str:
    return (
        "You are running an ORION provider benchmark. Output exactly one JSON object with no markdown, no code fences, "
        "and no explanation. The JSON must satisfy this schema and constants exactly. "
        f"Provider id to emit: {provider_id}. "
        f"Schema name: {case['schema_name']}. "
        f"Schema: {compact_json(case['schema'])}. "
        f"Scenario instructions: {case['user_prompt']}"
    )


def parse_json_text(text: str) -> dict[str, Any] | None:
    txt = (text or "").strip()
    if not txt:
        return None
    try:
        obj = json.loads(txt)
        return obj if isinstance(obj, dict) else None
    except Exception:
        start = txt.find("{")
        end = txt.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(txt[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
    return None


def json_value_matches(schema: dict[str, Any], value: Any) -> bool:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            return False
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                return False
        if schema.get("additionalProperties") is False:
            allowed = set(properties)
            if any(key not in allowed for key in value):
                return False
        for key, subschema in properties.items():
            if key in value and not json_value_matches(subschema, value[key]):
                return False
        return True
    if schema_type == "array":
        if not isinstance(value, list):
            return False
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            return False
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            return all(json_value_matches(item_schema, item) for item in value)
        return True
    if schema_type == "string":
        if not isinstance(value, str):
            return False
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            return False
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            return False
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    elif schema_type is not None:
        return False

    if "const" in schema and value != schema["const"]:
        return False
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False
    return True


def validate_case_payload(case: BenchCase, payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and json_value_matches(case["schema"], payload)


def first_non_empty_text(values: list[str | None]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def http_post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout_s: float = DEFAULT_TIMEOUT_S) -> tuple[int, dict[str, Any] | None]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, method="POST", data=data, headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            payload = None
        return int(exc.code or 500), payload if isinstance(payload, dict) else None
    except Exception:
        return 0, None




def http_get_json(url: str, headers: dict[str, str], timeout_s: float = DEFAULT_TIMEOUT_S) -> tuple[int, dict[str, Any] | None]:
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            payload = None
        return int(exc.code or 500), payload if isinstance(payload, dict) else None
    except Exception:
        return 0, None

def response_text_from_payload(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    outputs = payload.get("output")
    if isinstance(outputs, list):
        for output in outputs:
            if not isinstance(output, dict):
                continue
            content = output.get("content")
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = first_non_empty_text([
                        item.get("text") if isinstance(item.get("text"), str) else None,
                        item.get("output_text") if isinstance(item.get("output_text"), str) else None,
                    ])
                    if text:
                        return text
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = first_non_empty_text([
                        item.get("text") if isinstance(item.get("text"), str) else None,
                        item.get("content") if isinstance(item.get("content"), str) else None,
                    ])
                    if text:
                        return text
    return ""


def finish_reason_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("finish_reason"), str):
        return payload["finish_reason"]
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        finish_reason = (choices[0] or {}).get("finish_reason")
        if isinstance(finish_reason, str):
            return finish_reason
    return None


def usage_cost_estimate(payload: dict[str, Any] | None) -> float:
    if not isinstance(payload, dict):
        return 0.0
    usage = payload.get("usage") or {}
    total_tokens = usage.get("total_tokens")
    if not isinstance(total_tokens, (int, float)):
        return 0.0
    return float(total_tokens) * 0.0


def probe_openai_responses(key: str, model: str) -> tuple[bool, str]:
    status, payload = http_post_json(
        "https://api.openai.com/v1/responses",
        {"authorization": f"Bearer {key}"},
        {
            "model": model,
            "input": "Return exactly {\"ready\":true}",
            "max_output_tokens": 32,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "openai_lane_probe",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"ready": {"type": "boolean", "const": True}},
                        "required": ["ready"],
                    },
                    "strict": True,
                }
            },
        },
        timeout_s=min(DEFAULT_TIMEOUT_S, 20.0),
    )
    if status != 200 or not payload:
        error = ((payload or {}).get("error") or {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        return False, f"responses probe failed ({status}): {message or 'no payload'}"
    text = response_text_from_payload(payload)
    parsed = parse_json_text(text)
    if not isinstance(parsed, dict) or parsed.get("ready") is not True:
        return False, "responses probe returned non-schema output"
    return True, "ready"


def openrouter_attribution_headers() -> dict[str, str]:
    return {
        "HTTP-Referer": OPENROUTER_HTTP_REFERER,
        "X-Title": OPENROUTER_X_TITLE,
    }


def openrouter_headers(key: str) -> dict[str, str]:
    return {"authorization": f"Bearer {key}", **openrouter_attribution_headers()}


def probe_openrouter_chat_completions(key: str, model: str) -> tuple[bool, str]:
    status, payload = http_post_json(
        urllib.parse.urljoin(OPENROUTER_BASE_URL.rstrip("/") + "/", "chat/completions"),
        openrouter_headers(key),
        {
            "model": model,
            "messages": [{"role": "user", "content": "Return exactly {\"ready\":true}"}],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "openrouter_lane_probe",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"ready": {"type": "boolean", "const": True}},
                        "required": ["ready"],
                    },
                    "strict": True,
                },
            },
            "provider": {"require_parameters": True},
            "max_tokens": 32,
        },
        timeout_s=min(DEFAULT_TIMEOUT_S, 20.0),
    )
    if status != 200 or not payload:
        error = ((payload or {}).get("error") or {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        return False, f"openrouter probe failed ({status}): {message or 'no payload'}"
    text = response_text_from_payload(payload)
    parsed = parse_json_text(text)
    if not isinstance(parsed, dict) or parsed.get("ready") is not True:
        return False, "openrouter probe returned non-schema output"
    return True, "ready"


def provider_readiness(provider_id: str, provider: dict[str, Any], live: bool) -> dict[str, Any]:
    ready = False
    note = "unknown provider"
    if provider_id == "gemini-openclaw":
        ready = shutil.which("openclaw") is not None
        note = "openclaw available" if ready else "openclaw binary not found"
    elif provider_id == "openai-control-plane":
        key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            return {"provider_ready": False, "skip_reason": "missing OPENAI_API_KEY"}
        model = (os.getenv("OPENAI_BENCHMARK_MODEL") or provider["models"][0]).strip()
        if not live:
            return {"provider_ready": True, "skip_reason": "ready (probe skipped in dry-run/readiness mode)", "model_requested": model}
        ok, message = probe_openai_responses(key, model)
        return {"provider_ready": ok, "skip_reason": message if not ok else "", "model_requested": model}
    elif provider_id.startswith("openrouter-"):
        key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not key:
            return {"provider_ready": False, "skip_reason": "missing OPENROUTER_API_KEY"}
        model = (os.getenv("OPENROUTER_BENCHMARK_MODEL") or provider["models"][0]).strip()
        if not live:
            return {"provider_ready": True, "skip_reason": "ready (probe skipped in dry-run/readiness mode)", "model_requested": model}
        ok, message = probe_openrouter_chat_completions(key, model)
        return {"provider_ready": ok, "skip_reason": message if not ok else "", "model_requested": model}
    elif provider_id == "kimi-k2-5-nvidia-build":
        key = (os.getenv("NVIDIA_API_KEY") or "").strip()
        ready = bool(key)
        note = "ready" if ready else "missing NVIDIA_API_KEY"
    elif provider_id == "local-bounded-runtime":
        base_url = (os.getenv("LOCAL_LLM_BASE_URL") or "http://127.0.0.1:1234/v1").strip()
        status, payload = http_get_json(
            urllib.parse.urljoin(base_url.rstrip("/") + "/", "models"),
            {"authorization": f"Bearer {(os.getenv('LOCAL_LLM_API_KEY') or 'local').strip()}"},
            timeout_s=min(DEFAULT_TIMEOUT_S, 10.0),
        )
        ready = status == 200 and isinstance(payload, dict)
        note = "ready" if ready else f"local server not ready at {base_url}"
    return {"provider_ready": ready, "skip_reason": "" if ready else note}


def benchmark_row_base(provider_id: str, provider: dict[str, Any], task_id: str, case: BenchCase) -> dict[str, Any]:
    return {
        "provider": provider_id,
        "scenario": task_id,
        "pass_fail": "pending",
        "provider_ready": False,
        "request_surface": provider.get("api_surface", "unknown"),
        "response_format_used": "unknown",
        "schema_name": case["schema_name"],
        "schema_enforced": False,
        "model_requested": "",
        "model_used": "",
        "http_status": 0,
        "exit_code": 0,
        "finish_reason": "",
        "error_code": "",
        "error_message": "",
        "skip_reason": "",
        "latency_ms": 0.0,
        "cost_estimate": 0.0,
        "tool_success_rate": 0.0,
        "schema_failure_rate": 0.0,
        "notes": "",
    }


def bench_openclaw(provider_id: str, provider: dict[str, Any], task_id: str) -> dict[str, Any]:
    case = bench_case(task_id)
    row = benchmark_row_base(provider_id, provider, task_id, case)
    row.update(
        {
            "provider_ready": True,
            "request_surface": "openclaw-agent-local-json",
            "response_format_used": "prompt_embedded_json_schema",
            "schema_enforced": False,
            "model_requested": provider["models"][0],
        }
    )
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [
                "openclaw",
                "agent",
                "--agent",
                "main",
                "--local",
                "--json",
                "--thinking",
                "minimal",
                "--message",
                embedded_schema_prompt(case, provider_id),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        row.update({"error_message": "openclaw binary not found", "schema_failure_rate": 1.0})
        return row
    row["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    row["exit_code"] = int(proc.returncode)
    if proc.returncode != 0:
        row.update({"pass_fail": "fail", "error_message": (proc.stderr or proc.stdout).strip()[:400], "schema_failure_rate": 1.0})
        return row
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        row.update({"pass_fail": "fail", "error_message": "openclaw output was not valid JSON envelope", "schema_failure_rate": 1.0})
        return row
    texts: list[str] = []
    for item in (((payload or {}).get("result") or {}).get("payloads") or []):
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    raw_text = "\n".join(texts)
    parsed = parse_json_text(raw_text)
    ok = validate_case_payload(case, parsed)
    row.update(
        {
            "pass_fail": "pass" if ok else "fail",
            "tool_success_rate": 1.0 if ok else 0.0,
            "schema_failure_rate": 0.0 if ok else 1.0,
            "notes": "schema validated via embedded prompt contract" if ok else raw_text[:400],
        }
    )
    return row


def bench_openai(provider_id: str, provider: dict[str, Any], task_id: str) -> dict[str, Any]:
    case = bench_case(task_id)
    row = benchmark_row_base(provider_id, provider, task_id, case)
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_BENCHMARK_MODEL") or provider["models"][0]).strip()
    row.update(
        {
            "provider_ready": bool(key),
            "request_surface": "openai-responses-api",
            "response_format_used": "json_schema",
            "schema_enforced": True,
            "model_requested": model,
        }
    )
    if not key:
        row["skip_reason"] = "missing OPENAI_API_KEY"
        row["notes"] = "Set OPENAI_API_KEY, then rerun the live benchmark suite."
        return row
    started = time.perf_counter()
    status, payload = http_post_json(
        "https://api.openai.com/v1/responses",
        {"authorization": f"Bearer {key}"},
        {
            "model": model,
            "instructions": "Return only schema-valid JSON for the benchmark. No markdown, no prose.",
            "input": f"Provider id to emit: {provider_id}. {case['user_prompt']}",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": case["schema_name"],
                    "schema": case["schema"],
                    "strict": True,
                }
            },
        },
    )
    row["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    row["http_status"] = status
    if status != 200 or not payload:
        error = ((payload or {}).get("error") or {}) if isinstance(payload, dict) else {}
        row.update(
            {
                "pass_fail": "fail",
                "error_code": str(error.get("code") or ""),
                "error_message": str(error.get("message") or "responses request failed"),
                "schema_failure_rate": 1.0,
            }
        )
        return row
    text = response_text_from_payload(payload)
    parsed = parse_json_text(text)
    ok = validate_case_payload(case, parsed)
    row.update(
        {
            "pass_fail": "pass" if ok else "fail",
            "model_used": str(payload.get("model") or model),
            "finish_reason": finish_reason_from_payload(payload) or "",
            "cost_estimate": round(usage_cost_estimate(payload), 6),
            "tool_success_rate": 1.0 if ok else 0.0,
            "schema_failure_rate": 0.0 if ok else 1.0,
            "notes": "strict json_schema via Responses API" if ok else text[:400],
        }
    )
    return row


def bench_openai_compatible(
    provider_id: str,
    provider: dict[str, Any],
    task_id: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    request_surface: str,
    extra_headers: dict[str, str] | None = None,
    require_parameters: bool = False,
) -> dict[str, Any]:
    case = bench_case(task_id)
    row = benchmark_row_base(provider_id, provider, task_id, case)
    row.update(
        {
            "provider_ready": bool(api_key),
            "request_surface": request_surface,
            "response_format_used": "json_schema",
            "schema_enforced": True,
            "model_requested": model,
        }
    )
    if not api_key:
        if provider_id == "kimi-k2-5-nvidia-build":
            env_name = "NVIDIA_API_KEY"
        elif provider_id.startswith("openrouter-"):
            env_name = "OPENROUTER_API_KEY"
        else:
            env_name = "LOCAL_LLM_API_KEY/LOCAL_LLM_BASE_URL"
        row["skip_reason"] = f"missing {env_name}"
        return row
    request_headers = {"authorization": f"Bearer {api_key}"}
    if isinstance(extra_headers, dict):
        request_headers.update(extra_headers)
    request_body: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Return only schema-valid JSON for the benchmark. No markdown, no prose."},
            {"role": "user", "content": f"Provider id to emit: {provider_id}. {case['user_prompt']}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": case["schema_name"],
                "schema": case["schema"],
                "strict": True,
            },
        },
    }
    if require_parameters:
        request_body["provider"] = {"require_parameters": True}
    started = time.perf_counter()
    status, payload = http_post_json(
        urllib.parse.urljoin(base_url.rstrip("/") + "/", "chat/completions"),
        request_headers,
        request_body,
    )
    row["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    row["http_status"] = status
    if status != 200 or not payload:
        error = ((payload or {}).get("error") or {}) if isinstance(payload, dict) else {}
        row.update(
            {
                "pass_fail": "fail",
                "error_code": str(error.get("code") or ""),
                "error_message": str(error.get("message") or "chat completions request failed"),
                "schema_failure_rate": 1.0,
            }
        )
        return row
    text = response_text_from_payload(payload)
    parsed = parse_json_text(text)
    ok = validate_case_payload(case, parsed)
    row.update(
        {
            "pass_fail": "pass" if ok else "fail",
            "model_used": str(payload.get("model") or model),
            "finish_reason": finish_reason_from_payload(payload) or "",
            "cost_estimate": round(usage_cost_estimate(payload), 6),
            "tool_success_rate": 1.0 if ok else 0.0,
            "schema_failure_rate": 0.0 if ok else 1.0,
            "notes": "json_schema via chat completions" if ok else text[:400],
        }
    )
    return row


def maybe_trace(results: list[dict[str, Any]], dry_run: bool) -> None:
    events_path = ROOT / "eval" / "provider_benchmark_events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    if dry_run:
        return

    public_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()
    if not public_key or not secret_key:
        return

    try:
        from langfuse import Langfuse
    except Exception:
        return

    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=(os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip(),
    )
    trace_id = langfuse.create_trace_id()
    with langfuse.start_as_current_observation(
        name="llm-provider-benchmark",
        as_type="span",
        trace_context={"trace_id": trace_id},
        input={"results": len(results)},
    ) as root:
        for row in results:
            with root.start_as_current_observation(name=f'{row["provider"]}:{row["scenario"]}') as child:
                child.update(output=row)
    langfuse.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ORION provider benchmarks with provider-specific schema requests.")
    parser.add_argument("--providers", default="", help="Comma-separated provider ids (default: all)")
    parser.add_argument("--tasks", default="", help="Comma-separated task ids (default: all)")
    parser.add_argument("--output-json", default=str(ROOT / "eval" / "llm_provider_benchmark_latest.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trace", action="store_true", help="Emit local JSONL events and Langfuse traces when configured.")
    parser.add_argument("--check-readiness", action="store_true", help="Print provider readiness and exit without running benchmarks.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero when a readiness check finds an unavailable provider.")
    args = parser.parse_args()

    registry = load_json(REGISTRY_PATH)
    matrix = load_json(MATRIX_PATH)
    template = load_json(TEMPLATE_PATH)
    provider_map = {item["provider_id"]: item for item in registry["providers"]}
    tasks = matrix["tasks"]

    selected_providers = set(filter(None, [part.strip() for part in args.providers.split(",")])) or set(provider_map)
    selected_tasks = set(filter(None, [part.strip() for part in args.tasks.split(",")])) or {item["task_id"] for item in tasks}

    readiness_rows = []
    for provider_id in provider_map:
        if provider_id not in selected_providers:
            continue
        readiness = provider_readiness(provider_id, provider_map[provider_id], live=not args.dry_run and args.check_readiness)
        readiness_rows.append({"provider": provider_id, **readiness})
    if args.check_readiness:
        print(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "providers": readiness_rows}, indent=2, sort_keys=True))
        if args.require_ready and any(not item.get("provider_ready") for item in readiness_rows):
            return 1
        return 0

    results: list[dict[str, Any]] = []
    for task in tasks:
        task_id = task["task_id"]
        if task_id not in selected_tasks:
            continue
        providers = [task["primary_provider"], *task["fallback_providers"]]
        for provider_id in providers:
            if provider_id not in selected_providers:
                continue
            provider = provider_map[provider_id]
            case = bench_case(task_id)
            if args.dry_run:
                row = benchmark_row_base(provider_id, provider, task_id, case)
                row.update(
                    {
                        "pass_fail": "pass",
                        "provider_ready": True,
                        "request_surface": provider.get("api_surface", "unknown"),
                        "response_format_used": "dry_run",
                        "schema_enforced": bool(provider.get("requires_schema")),
                        "model_requested": str((provider.get("models") or [""])[0]),
                        "tool_success_rate": 1.0,
                        "notes": "dry run placeholder",
                    }
                )
            elif provider_id == "gemini-openclaw":
                row = bench_openclaw(provider_id, provider, task_id)
            elif provider_id == "openai-control-plane":
                row = bench_openai(provider_id, provider, task_id)
            elif provider_id == "kimi-k2-5-nvidia-build":
                row = bench_openai_compatible(
                    provider_id,
                    provider,
                    task_id,
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=(os.getenv("NVIDIA_API_KEY") or "").strip(),
                    model=str((provider.get("models") or [""])[0]),
                    request_surface="nvidia-build-chat-completions",
                )
            elif provider_id.startswith("openrouter-"):
                row = bench_openai_compatible(
                    provider_id,
                    provider,
                    task_id,
                    base_url=OPENROUTER_BASE_URL,
                    api_key=(os.getenv("OPENROUTER_API_KEY") or "").strip(),
                    model=(os.getenv("OPENROUTER_BENCHMARK_MODEL") or str((provider.get("models") or [""])[0])).strip(),
                    request_surface="openrouter-chat-completions",
                    extra_headers=openrouter_attribution_headers(),
                    require_parameters=True,
                )
            else:
                row = bench_openai_compatible(
                    provider_id,
                    provider,
                    task_id,
                    base_url=(os.getenv("LOCAL_LLM_BASE_URL") or "http://127.0.0.1:1234/v1").strip(),
                    api_key=(os.getenv("LOCAL_LLM_API_KEY") or "local").strip(),
                    model=(os.getenv("LOCAL_LLM_MODEL") or "qwen3.5-4b-mlx").strip(),
                    request_surface="openai-compatible-local-chat-completions",
                )
            if row["pass_fail"] not in ALLOWED_PASS_FAIL:
                row["pass_fail"] = "fail"
            results.append(row)

    output = {
        **template,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_mode": "dry_run" if args.dry_run else "live",
        "results": results,
        "summary": {
            "primary_candidate": "openrouter-auto-primary",
            "promotion_recommended": bool(results) and all(item["pass_fail"] == "pass" for item in results),
            "notes": "Dry-run rows are placeholders. Live promotion requires provider-ready pass results.",
            "unready_providers": sorted({item["provider"] for item in results if not item["provider_ready"]}),
        },
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")

    if args.trace:
        maybe_trace(results, args.dry_run)

    print(f"LLM_PROVIDER_BENCHMARK_OK {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
