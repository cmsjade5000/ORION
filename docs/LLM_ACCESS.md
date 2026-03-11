# LLM Access: Near-Term Needs + Key Setup

This repo uses a **hybrid provider model**:
- OpenClaw model routing for the live ORION production lane
- Direct provider APIs for control/eval and benchmark lanes
- Provider auth stored in the Keep (not in Git)
- A few skills that call provider APIs directly (example: Gemini image generation)

This doc is a practical checklist for the next ~3-6 months.

## Likely LLM Needs (Near Future)

- **General chat + orchestration:** strong instruction-following, reliable tool-calling, low latency.
- **Fallbacks:** provider/model outages happen; you want at least one backup.
- **Cost control:** inexpensive default model for routine tasks; optional “bigger” model for hard problems.
- **Retrieval summaries:** fast, cheap summarization for RSS/news/email workflows.
- **Multimodal (images):** ORION image generation uses the `nano-banana-pro` skill (Gemini API).

## Recommended Provider Setup (Restricted)

This repo is currently structured around four lanes:

1. **Google Gemini** for primary ORION chat routing (preferred: Gemini 2.5 Flash Lite).
2. **OpenAI API** for control-plane/eval/trace-grading tasks.
3. Optional: **NVIDIA Build** (nvapi-...) for **Kimi 2.5** fallback and reasoning benchmarks.
4. Optional: **Local OpenAI-compatible runtime** (LM Studio/Ollama/vLLM) for bounded utility tasks.

## Where To Get Keys (You Do This Part)

- Google Gemini API key: https://aistudio.google.com/app/apikey

Optional (only if you enable Kimi 2.5 fallback):
- NVIDIA Build API key (nvapi-...) from NVIDIA Build

Optional:
- OpenAI API key for control/eval lane
- Local runtime URL/key if your local server requires one

## Wire It Into Gateway (No Secrets In Git)

### 1) OpenClaw provider auth (recommended)

Prefer `openclaw models auth paste-token` so the LaunchAgent gateway service can use it reliably.

```bash
# Google (Gemini)
openclaw models auth paste-token --provider google
```

Verify:

```bash
openclaw models status --probe
```

### 2) Gemini key for the `nano-banana-pro` image skill

The workspace fallback skill reads the key from either:
- `GEMINI_API_KEY`, or
- `~/.openclaw/secrets/gemini.api_key` (recommended)

Create the secret file (contains only the raw key + newline):

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
printf '%s\n' '<your-gemini-api-key>' > ~/.openclaw/secrets/gemini.api_key
chmod 600 ~/.openclaw/secrets/gemini.api_key
```

### 3) Model routing choices (optional)

Default (recommended) routing:

```bash
openclaw models set google/gemini-2.5-flash-lite
openclaw models fallbacks clear
openclaw models fallbacks add google/gemini-2.5-flash-lite
```

### 4) OpenAI control lane

Store `OPENAI_API_KEY` in `~/.openclaw/.env` or your shell when running eval/benchmark scripts.

OpenAI is treated as a direct API lane for:
- structured outputs
- eval generation
- trace grading
- tool contract testing

The benchmark harness now uses the OpenAI Responses API with strict `json_schema` formatting for this lane.
It is intentionally not the default ORION production model without benchmark evidence.

### 5) Kimi + local provider wiring helper

Use the repo helper to register NVIDIA Build and local LM Studio in the runtime config:

```bash
scripts/openclaw_configure_llm_providers.sh --dry-run
scripts/openclaw_configure_llm_providers.sh --include-kimi-fallback
```

### 6) Provider benchmarks and tracing

Check lane readiness before a live run:

```bash
python3 scripts/run_llm_provider_benchmarks.py --check-readiness
python3 scripts/run_llm_provider_benchmarks.py --check-readiness --providers openai-control-plane
python3 scripts/run_llm_provider_benchmarks.py --check-readiness --require-ready --providers openai-control-plane
```

Run a dry-run benchmark matrix:

```bash
python3 scripts/run_llm_provider_benchmarks.py --dry-run --trace
```

Run the hosted live suite the moment `OPENAI_API_KEY` exists:

```bash
python3 scripts/run_llm_provider_benchmarks.py \
  --providers gemini-openclaw,openai-control-plane,kimi-k2-5-nvidia-build \
  --trace
```

Run a targeted OpenAI control-plane benchmark:

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
- `LLM_BENCHMARK_TIMEOUT_S`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, the benchmark script will also emit Langfuse traces.

## Notes

- Secrets belong in `~/.openclaw/` per `KEEP.md`. Never paste keys into chat or commit them.
- `openclaw.yaml` / `openclaw.json.example` are templates only; runtime config is `~/.openclaw/openclaw.json`.
- For supported credential fields in runtime config, prefer SecretRef objects over raw `${ENV}` strings so `openclaw secrets` audit/planning flows can inspect them cleanly.
