# LLM Access: Near-Term Needs + Key Setup

This repo uses a **low-cost-first provider model**:
- OpenRouter as the default hosted runtime lane
- local or free/cheap lanes for bounded work whenever possible
- OpenAI only as an explicit premium lane
- Provider auth stored in the Keep (not in Git)

This doc is a practical checklist for the next ~3-6 months.

## Likely LLM Needs (Near Future)

- **General chat + orchestration:** strong instruction-following, reliable tool-calling, low latency.
- **Fallbacks:** provider/model outages happen; you want at least one backup.
- **Cost control:** inexpensive default model for routine tasks; optional bigger model for hard problems.
- **Retrieval summaries:** fast, cheap summarization for RSS/news/email workflows.

## Recommended Provider Setup (Low-Cost Default, Premium Optional)

1. **OpenRouter free/default lane** is the checked-in runtime default for ORION.
2. **OpenRouter auto** lane (`openrouter-auto-primary`) is the main hosted orchestration lane when you need more headroom.
3. **OpenRouter Hunter Alpha** lane (`openrouter-hunter-alpha`) is for non-sensitive research only.
4. **Local runtime** and **OpenRouter free bounded** stay preferred for bounded utility work.
5. Optional premium/specialist lanes stay available: OpenAI control plane and NVIDIA Build Kimi.

## Where To Get Keys (You Do This Part)

- OpenRouter API key for the default hosted runtime lane
- Optional OpenAI API key only if you intentionally enable the premium lane

Optional compatibility keys:
- NVIDIA Build API key (nvapi-...) for Kimi compatibility fallback
- Local runtime URL/key if your local server requires one

## Wire It Into Gateway (No Secrets In Git)

### 1) OpenClaw provider auth (recommended)

Prefer `openclaw models auth paste-token` so the LaunchAgent gateway service can use it reliably.

```bash
# Default hosted lane auth
openclaw models auth paste-token --provider openrouter

# Optional premium lane auth
openclaw models auth paste-token --provider openai
```

Verify:

```bash
openclaw models status
```

### 2) OPENROUTER_API_KEY for the default hosted lane

Store the default hosted-lane key in Keep-backed secrets:

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

### 3) OPENAI_API_KEY for the premium lane

Only set this if you intentionally want the premium OpenAI lane:

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

### 4) Provider wiring helper

Use the repo helper to wire the low-cost default model plus cheap/free fallbacks:

```bash
scripts/openclaw_configure_llm_providers.sh --dry-run
scripts/openclaw_configure_llm_providers.sh
scripts/openclaw_configure_llm_providers.sh --primary-model openrouter/openrouter/free --include-kimi-fallback
scripts/openclaw_configure_llm_providers.sh --primary-model openai/gpt-5.4
```

### 5) Low-cost-first readiness checks and benchmark commands

Readiness checks for the default hosted lane:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openrouter-auto-primary

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --providers openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded,local-bounded-runtime

python3 scripts/run_llm_provider_benchmarks.py \
  --check-readiness \
  --require-ready \
  --providers openrouter-auto-primary
```

Targeted low-cost hosted benchmark:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openrouter-auto-primary \
  --trace
```

Low-cost live matrix:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers openrouter-auto-primary,openrouter-hunter-alpha,openrouter-free-bounded,local-bounded-runtime,openai-control-plane,kimi-k2-5-nvidia-build \
  --trace
```

### 6) Targeted premium OpenAI control/eval runs

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
- Normal repo planning/code-mod work should stay in low-cost mode and avoid live benchmark runs unless you are intentionally validating provider posture.
- For supported credential fields in runtime config, prefer SecretRef objects over raw `${ENV}` strings so `openclaw secrets` audit/planning flows can inspect them cleanly.
