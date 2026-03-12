# LLM Provider Matrix

This file is the durable routing reference for ORION's OpenRouter-first, multi-provider LLM setup.

Machine-readable sources:
- `config/llm_provider_registry.json`
- `config/llm_task_routing_matrix.json`
- `config/llm_provider_benchmark_report.template.json`

Operational helpers:
- `scripts/openclaw_configure_llm_providers.sh`
- `scripts/run_llm_provider_benchmarks.py`

## Provider lanes (OpenRouter-first)

| Provider | Lane | Primary use | Promotion rule |
| --- | --- | --- | --- |
| OpenRouter (`openrouter/auto`) | openrouter-auto-primary | Live ORION routing, handoffs, and default day-to-day tool selection | Stays default unless rollback evidence requires compatibility fallback |
| OpenRouter (`hunter-alpha`) | openrouter-hunter-alpha | Non-sensitive research synthesis and second opinions | Non-sensitive only; prompts/completions are provider-logged |
| OpenRouter (free-tier bounded model) | openrouter-free-bounded | Bounded utility tasks (summarization, extraction, tagging) | Never owns high-stakes orchestration |

## Compatibility lanes (backward-compatible)

| Provider | Lane | Primary use | Promotion rule |
| --- | --- | --- | --- |
| Gemini via OpenClaw | production-fallback | Legacy production fallback and rollback lane | Can be promoted only with benchmark evidence and rollback notes |
| OpenAI Responses API | control-eval | Structured outputs, tool contract tests, eval generation, trace grading | Never becomes primary silently |
| Kimi K2.5 via NVIDIA Build | reasoning-tertiary | Tertiary hosted reasoning fallback | Must pass ORION-specific evals before fallback promotion |
| Local runtime | bounded-local-backup | Optional local bounded utility work | Never owns high-stakes orchestration |

## Task routing defaults

| Task | Primary | Fallbacks | Local allowed |
| --- | --- | --- | --- |
| Routing and specialist handoffs | openrouter-auto-primary | Gemini, OpenAI, Kimi (tertiary) | no |
| Structured output and tool validation | OpenAI | openrouter-auto-primary, Gemini, Kimi (tertiary) | no |
| Research and second opinions | openrouter-hunter-alpha | openrouter-auto-primary, OpenAI, Kimi (tertiary) | no |
| Evals and trace grading | OpenAI | openrouter-auto-primary, Gemini, Kimi (tertiary) | no |
| Bounded utility work | openrouter-free-bounded | Local, openrouter-auto-primary | yes |

## Hard rules

- All action-producing outputs must validate against a schema before execution.
- High-risk, destructive, or external-delivery actions still require human approval.
- Hunter Alpha is non-sensitive-only because provider logs prompts/completions; do not send secrets, credentials, or regulated personal data.
- Local models do not own specialist orchestration, approval gates, or external messaging decisions.
- NVIDIA Build Kimi remains a tertiary fallback lane unless benchmark evidence explicitly promotes it.
- Provider changes require benchmark evidence and rollback notes.

## Benchmark contract

Use `config/llm_provider_benchmark_report.template.json` as the baseline report shape.

Provider-specific request surfaces in the harness:
- OpenRouter auto primary: OpenRouter API with model `openrouter/auto`
- OpenRouter Hunter Alpha: OpenRouter API with provider-specific Hunter Alpha model id
- OpenRouter free bounded: OpenRouter API with bounded/free-tier model id
- Gemini via OpenClaw: embedded schema prompt through `openclaw agent --local --json`
- OpenAI control plane: Responses API with strict `text.format.type=json_schema`
- Kimi via NVIDIA Build: OpenAI-compatible `chat/completions` with `response_format.json_schema`
- Local runtime (compatibility): OpenAI-compatible `chat/completions` with `response_format.json_schema`

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
