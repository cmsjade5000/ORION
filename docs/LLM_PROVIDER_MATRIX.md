# LLM Provider Matrix

This file is the durable routing reference for ORION's low-cost-first, multi-provider LLM setup.

Machine-readable sources:
- `config/llm_provider_registry.json`
- `config/llm_task_routing_matrix.json`
- `config/llm_provider_benchmark_report.template.json`

Operational helpers:
- `scripts/openclaw_configure_llm_providers.sh`
- `scripts/run_llm_provider_benchmarks.py`

## Provider lanes (low-cost-first)

| Provider | Lane | Primary use | Promotion rule |
| --- | --- | --- | --- |
| OpenRouter (`openrouter/auto`) | openrouter-auto-primary | Default hosted ORION routing, handoffs, structured outputs, and eval control | Stays default unless rollback evidence requires a different low-cost lane |
| OpenAI Responses API | openai-control-plane | Premium opt-in control lane for hard cases, audits, or explicit user-approved spend | Never becomes ambient default without explicit promotion evidence |
| OpenRouter (`hunter-alpha`) | openrouter-hunter-alpha | Non-sensitive research synthesis and second opinions | Non-sensitive only; prompts/completions are provider-logged |
| OpenRouter (free-tier bounded model) | openrouter-free-bounded | Cheapest hosted lane for bounded utility tasks and low-stakes repo work | Never owns high-stakes orchestration |

## Compatibility lanes (backward-compatible)

| Provider | Lane | Primary use | Promotion rule |
| --- | --- | --- | --- |
| Kimi K2.5 via NVIDIA Build | kimi-specialist | Deliberate long-context, style-sensitive, and second-opinion lane; only a last-resort hosted fallback outside specialist routing | Must pass ORION-specific evals before fallback promotion |
| Local runtime | bounded-local-backup | Optional local bounded utility work | Never owns high-stakes orchestration |

## Task routing defaults

| Task | Primary | Fallbacks | Local allowed |
| --- | --- | --- | --- |
| Routing and specialist handoffs | OpenRouter auto | OpenRouter free bounded, then OpenAI, then Kimi | no |
| Structured output and tool validation | OpenRouter auto | OpenRouter free bounded, then OpenAI, then Kimi | no |
| Research and second opinions | OpenRouter auto | Hunter Alpha, OpenRouter free bounded, then OpenAI, then Kimi | no |
| Evals and trace grading | OpenRouter auto | OpenRouter free bounded, then OpenAI, then Kimi | no |
| Bounded utility work | Local | OpenRouter free bounded, OpenRouter auto, then OpenAI | yes |

## Hard rules

- All action-producing outputs must validate against a schema before execution.
- High-risk, destructive, or external-delivery actions still require human approval.
- Hunter Alpha is non-sensitive-only because provider logs prompts/completions; do not send secrets, credentials, or regulated personal data.
- Local models do not own specialist orchestration, approval gates, or external messaging decisions.
- Premium OpenAI/Codex lanes are explicit opt-in escalation paths, not the repo default.
- NVIDIA Build Kimi is an intentional specialist lane. Keep it out of hot-path production fallback chains for `main`/`ledger`, and place it after stable compatibility providers when it is present as a fallback at all.
- Provider changes require benchmark evidence and rollback notes.

## Benchmark contract

Use `config/llm_provider_benchmark_report.template.json` as the baseline report shape.

Provider-specific request surfaces in the harness:
- OpenAI control plane: Responses API with strict `text.format.type=json_schema`
- OpenRouter auto primary: OpenRouter API with model `openrouter/auto`
- OpenRouter Hunter Alpha: OpenRouter API with provider-specific Hunter Alpha model id
- OpenRouter free bounded: OpenRouter API with bounded/free-tier model id
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
