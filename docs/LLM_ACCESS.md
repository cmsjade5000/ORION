# LLM Access: Near-Term Needs + Key Setup

This repo uses an **OpenAI-first provider model**:
- OpenAI for live ORION runtime routing, structured outputs, and benchmark control
- OpenRouter only as an explicit compatibility fallback lane
- Provider auth stored in the Keep (not in Git)

This doc is a practical checklist for the next ~3-6 months.

## Likely LLM Needs (Near Future)

- **General chat + orchestration:** strong instruction-following, reliable tool-calling, low latency.
- **Fallbacks:** provider/model outages happen; you want at least one backup.
- **Cost control:** inexpensive default model for routine tasks; optional bigger model for hard problems.
- **Retrieval summaries:** fast, cheap summarization for RSS/news/email workflows.

## Recommended Provider Setup (OpenAI-First, Backward-Compatible)

1. **OpenAI** lane (`openai-control-plane`) is the default runtime route.
2. **OpenRouter auto** lane (`openrouter-auto-primary`) is the main compatibility fallback.
3. **OpenRouter Hunter Alpha** lane (`openrouter-hunter-alpha`) is for non-sensitive research only.
4. **OpenRouter free bounded** lane (`openrouter-free-bounded`) is for bounded utility work.
5. Optional compatibility lanes stay available: NVIDIA Build Kimi (intentional tertiary fallback) and local runtime.

## Where To Get Keys (You Do This Part)

- OpenAI API key for the primary runtime lane
- OpenRouter API key for compatibility fallbacks

Optional compatibility keys:
- NVIDIA Build API key (nvapi-...) for Kimi compatibility fallback
- Local runtime URL/key if your local server requires one

## Wire It Into Gateway (No Secrets In Git)

### 1) OpenClaw provider auth (recommended)

Prefer `openclaw models auth paste-token` so the LaunchAgent gateway service can use it reliably.

```bash
# OpenAI (default runtime lane)
openclaw models auth paste-token --provider openai

# Compatibility lane auth (optional)
openclaw models auth paste-token --provider openrouter
```

Verify:

```bash
openclaw models status --probe
```

### 2) OPENAI_API_KEY for the primary lane

Set `OPENAI_API_KEY` via Keep-backed secrets:

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
printf '%s\n' '<your-openai-api-key>' > ~/.openclaw/secrets/openai.api_key
chmod 600 ~/.openclaw/secrets/openai.api_key
```

For one shell session:

```bash
export OPENAI_API_KEY="$(cat ~/.openclaw/secrets/openai.api_key)"
```

### 3) OPENROUTER_API_KEY for compatibility fallbacks

Store the fallback key separately so it is easy to revoke without touching the OpenAI primary lane.

### 4) Provider wiring helper

Use the repo helper to wire the OpenAI primary model plus compatibility fallbacks:

```bash
scripts/openclaw_configure_llm_providers.sh --dry-run
scripts/openclaw_configure_llm_providers.sh --openai-primary-model openai/gpt-5.4
scripts/openclaw_configure_llm_providers.sh --include-kimi-fallback
```

### 5) OpenAI-first readiness checks and benchmark commands

Readiness checks for the OpenAI primary lane:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openai-control-plane

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openai-control-plane,openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --require-ready \
  --providers openai-control-plane
```

Targeted OpenAI primary benchmark:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openai-control-plane \
  --trace
```

OpenAI-first live matrix:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openai-control-plane,openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded,kimi-k2-5-nvidia-build \
  --trace
```

### 6) Targeted OpenAI control/eval runs

Store `OPENAI_API_KEY` in `~/.openclaw/.env` or your shell when running eval/benchmark scripts.

```bash
OPENAI_BENCHMARK_MODEL=${OPENAI_BENCHMARK_MODEL:-gpt-5} \
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openai-control-plane \
  --tasks structured_output_validation,evals_and_trace_grading \
  --trace
```

Relevant env vars:
- `OPENAI_API_KEY`
- `OPENAI_BENCHMARK_MODEL`
- `OPENROUTER_API_KEY`
- `LLM_BENCHMARK_TIMEOUT_S`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, the benchmark script will also emit Langfuse traces.

## Notes

- Hunter Alpha is a non-sensitive lane only. Treat prompts/completions as provider-logged and do not send secrets, credentials, or regulated personal data.
- Secrets belong in `~/.openclaw/` per `KEEP.md`. Never paste keys into chat or commit them.
- `openclaw.yaml` / `openclaw.json.example` are templates only; runtime config is `~/.openclaw/openclaw.json`.
- For supported credential fields in runtime config, prefer SecretRef objects over raw `${ENV}` strings so `openclaw secrets` audit/planning flows can inspect them cleanly.
