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

## Recommended Provider Setup (Restricted)

This repo is currently configured to use only:

1. **Google Gemini** for primary chat routing (preferred: Gemini 2.5 Flash Lite).
2. Optional: **NVIDIA Build** (nvapi-...) for **Kimi 2.5** fallback routing.

## Where To Get Keys (You Do This Part)

- Google Gemini API key: https://aistudio.google.com/app/apikey

Optional (only if you enable Kimi 2.5 fallback):
- NVIDIA Build API key (nvapi-...) from NVIDIA Build

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

## Notes

- Secrets belong in `~/.openclaw/` per `KEEP.md`. Never paste keys into chat or commit them.
- `openclaw.yaml` / `openclaw.json.example` are templates only; runtime config is `~/.openclaw/openclaw.json`.
