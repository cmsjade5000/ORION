# LLM Access: Near-Term Needs + Key Setup

This repo uses a **hybrid provider model**:
- OpenRouter-first routing for live ORION runtime lanes
- Direct provider APIs for control/eval and benchmark lanes
- Provider auth stored in the Keep (not in Git)
- A few skills that call provider APIs directly (example: Gemini image generation)

This doc is a practical checklist for the next ~3-6 months.

## Likely LLM Needs (Near Future)

- **General chat + orchestration:** strong instruction-following, reliable tool-calling, low latency.
- **Fallbacks:** provider/model outages happen; you want at least one backup.
- **Cost control:** inexpensive default model for routine tasks; optional bigger model for hard problems.
- **Retrieval summaries:** fast, cheap summarization for RSS/news/email workflows.
- **Multimodal (images):** ORION image generation uses the `nano-banana-pro` skill (Gemini API).

## Recommended Provider Setup (OpenRouter-First, Backward-Compatible)

1. **OpenRouter auto** lane (`openrouter-auto-primary`) is the default runtime route.
2. **OpenRouter Hunter Alpha** lane (`openrouter-hunter-alpha`) is for non-sensitive research only.
3. **OpenRouter free bounded** lane (`openrouter-free-bounded`) is for bounded utility work.
4. Compatibility lanes stay available: Gemini, OpenAI control/eval, NVIDIA Build Kimi (tertiary fallback), and local runtime.

## Where To Get Keys (You Do This Part)

- OpenRouter API key: https://openrouter.ai/keys

Optional compatibility keys:
- Google Gemini API key: https://aistudio.google.com/app/apikey
- OpenAI API key for control/eval lane
- NVIDIA Build API key (nvapi-...) for Kimi compatibility fallback
- Local runtime URL/key if your local server requires one

## Wire It Into Gateway (No Secrets In Git)

### 1) OpenClaw provider auth (recommended)

Prefer `openclaw models auth paste-token` so the LaunchAgent gateway service can use it reliably.

```bash
# OpenRouter (default runtime lane)
openclaw models auth paste-token --provider openrouter

# Compatibility lane auth (optional)
openclaw models auth paste-token --provider google
```

Verify:

```bash
openclaw models status --probe
```

### 2) OPENROUTER_API_KEY for scripts and benchmarks

Set `OPENROUTER_API_KEY` via Keep-backed secrets:

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
printf '%s\n' '<your-openrouter-api-key>' > ~/.openclaw/secrets/openrouter.api_key
chmod 600 ~/.openclaw/secrets/openrouter.api_key
```

For one shell session:

```bash
export OPENROUTER_API_KEY="$(cat ~/.openclaw/secrets/openrouter.api_key)"
```

### 3) Gemini key for the `nano-banana-pro` image skill (compatibility)

The workspace fallback skill reads from either:
- `GEMINI_API_KEY`, or
- `~/.openclaw/secrets/gemini.api_key` (recommended)

```bash
printf '%s\n' '<your-gemini-api-key>' > ~/.openclaw/secrets/gemini.api_key
chmod 600 ~/.openclaw/secrets/gemini.api_key
```

### 4) Provider wiring helper

Use the repo helper to wire compatibility providers and fallback chains:

```bash
scripts/openclaw_configure_llm_providers.sh --dry-run
scripts/openclaw_configure_llm_providers.sh --include-kimi-fallback
```

### 5) OpenRouter readiness checks and benchmark commands

Readiness checks for OpenRouter-first lanes:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openrouter-auto-primary

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --require-ready \
  --providers openrouter-auto-primary
```

Targeted OpenRouter auto primary benchmark:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openrouter-auto-primary \
  --trace
```

OpenRouter + compatibility live matrix:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded,gemini-openclaw,openai-control-plane,kimi-k2-5-nvidia-build \
  --trace
```

### 6) OpenAI control lane (compatibility)

Store `OPENAI_API_KEY` in `~/.openclaw/.env` or your shell when running eval/benchmark scripts.

```bash
OPENAI_BENCHMARK_MODEL=${OPENAI_BENCHMARK_MODEL:-gpt-5} \
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openai-control-plane \
  --tasks structured_output_validation,evals_and_trace_grading \
  --trace
```

Relevant env vars:
- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BENCHMARK_MODEL`
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
