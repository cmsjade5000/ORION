# LLM Access: Near-Term Needs + Key Setup

This repo uses **OpenClaw** for model routing. The “LLM framework” here is:
- OpenClaw model routing (primary + fallbacks)
- Provider auth stored in the Keep (not in Git)
- A few skills that call provider APIs directly (example: Gemini image generation)

This doc is a practical checklist for the next ~3-6 months.

## Likely LLM Needs (Near Future)

- **General chat + orchestration:** strong instruction-following, reliable tool-calling, low latency.
- **Fallbacks:** provider/model outages happen; you want at least one backup.
- **Cost control:** inexpensive default model for routine tasks; optional “bigger” model for hard problems.
- **Retrieval summaries:** fast, cheap summarization for RSS/news/email workflows.
- **Multimodal (images):** ORION image generation uses the `nano-banana-pro` skill (Gemini API).

## Recommended “Easy Mode” Provider Setup

1. **OpenRouter** (one API key, many models) for primary chat + most fallbacks.
2. **Google Gemini API key** for:
   - `nano-banana-pro` image generation
   - optional Gemini fallback routing (if you choose to use it)

This keeps setup simple while preserving redundancy.

## Where To Get Keys (You Do This Part)

- OpenRouter API key: https://openrouter.ai/keys
- Google Gemini API key: https://aistudio.google.com/app/apikey

Optional (only if you want direct-provider keys instead of OpenRouter):
- OpenAI API key: https://platform.openai.com/api-keys
- Anthropic API key: https://console.anthropic.com/
- AWS Bedrock credentials: https://console.aws.amazon.com/bedrock/

Other “easy access” inference providers (optional):
- Groq: https://console.groq.com/keys
- Mistral: https://console.mistral.ai/
- Fireworks: https://fireworks.ai/

## Wire It Into Gateway (No Secrets In Git)

### 1) OpenClaw provider auth (recommended)

Prefer `openclaw models auth paste-token` so the LaunchAgent gateway service can use it reliably.

```bash
# OpenRouter (recommended primary)
openclaw models auth paste-token --provider openrouter

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

If you want OpenRouter as the default chat model:

```bash
openclaw models set openrouter/openai/gpt-4o-mini
openclaw models fallbacks set openrouter/anthropic/claude-3.5-haiku,google/gemini-2.5-flash-lite
```

If you want a “single key” posture (OpenRouter only), remove Google from fallbacks:

```bash
openclaw models fallbacks set openrouter/anthropic/claude-3.5-haiku
```

## Notes

- Secrets belong in `~/.openclaw/` per `KEEP.md`. Never paste keys into chat or commit them.
- `openclaw.yaml` / `openclaw.json.example` are templates only; runtime config is `~/.openclaw/openclaw.json`.
