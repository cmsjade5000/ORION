# LLM Provider Matrix

This file is the durable routing reference for ORION's multi-provider LLM setup.

Machine-readable sources:
- `config/llm_provider_registry.json`
- `config/llm_task_routing_matrix.json`
- `config/llm_provider_benchmark_report.template.json`

Operational helpers:
- `scripts/openclaw_configure_llm_providers.sh`
- `scripts/run_llm_provider_benchmarks.py`

## Provider lanes

| Provider | Lane | Primary use | Promotion rule |
| --- | --- | --- | --- |
| Gemini via OpenClaw | production-orchestrator | Live ORION routing, handoffs, day-to-day tool selection | Stays primary until another lane wins neutral-or-better benchmarks |
| OpenAI Responses API | control-eval | Structured outputs, tool contract tests, eval generation, trace grading | Never becomes primary silently |
| Kimi K2.5 via NVIDIA Build | reasoning-fallback | Research synthesis, second opinions, alternative plans | Must pass ORION-specific evals before fallback promotion |
| Local runtime | bounded-utility | Summarization, extraction, tagging, compression | Never owns high-stakes orchestration |

## Task routing defaults

| Task | Primary | Fallbacks | Local allowed |
| --- | --- | --- | --- |
| Routing and specialist handoffs | Gemini | OpenAI, Kimi | no |
| Structured output and tool validation | OpenAI | Gemini, Kimi | no |
| Research and second opinions | Kimi | OpenAI, Gemini | no |
| Evals and trace grading | OpenAI | Gemini, Kimi | no |
| Bounded utility work | Local | Gemini | yes |

## Hard rules

- All action-producing outputs must validate against a schema before execution.
- High-risk, destructive, or external-delivery actions still require human approval.
- Local models do not own specialist orchestration, approval gates, or external messaging decisions.
- Provider changes require benchmark evidence and rollback notes.

## Benchmark contract

Use `config/llm_provider_benchmark_report.template.json` as the baseline report shape.

Provider-specific request surfaces in the harness:
- Gemini via OpenClaw: embedded schema prompt through `openclaw agent --local --json`
- OpenAI control plane: Responses API with strict `text.format.type=json_schema`
- Kimi via NVIDIA Build: OpenAI-compatible `chat/completions` with `response_format.json_schema`
- Local runtime: OpenAI-compatible `chat/completions` with `response_format.json_schema`

A provider can be promoted only when all are true:
- routing safety stays green
- schema failure rate is neutral-or-better versus baseline
- tool success rate is neutral-or-better versus baseline
- latency and cost tradeoffs are documented
- rollback path is explicit

## Tracing

`scripts/run_llm_provider_benchmarks.py --trace` always appends local JSONL events to:
- `eval/provider_benchmark_events.jsonl`

Every result row now records transport and schema diagnostics, including readiness, request surface, schema mode, requested/used model, transport status, finish reason, and skip/error notes.

If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are configured and the `langfuse` package is installed, the same benchmark run also emits Langfuse traces.
