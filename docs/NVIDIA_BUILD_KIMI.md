# NVIDIA Build API (nvapi-...) + Kimi K2.5 (OpenClaw wiring)

Goal: let ORION use **OpenRouter** for Kimi K2.5 when available, and fall back to **NVIDIA Build** when OpenRouter is missing/unavailable.

This repo does **not** store secrets. Do not paste API keys into Git.

## 1) Put the NVIDIA key in the Keep

Preferred for gateway-service reliability: store provider keys in `~/.openclaw/.env`.

- Add a line:

```bash
NVIDIA_API_KEY=nvapi-...
```

- Lock down permissions:

```bash
chmod 600 ~/.openclaw/.env
```

## 2) Register NVIDIA Build as a custom provider in OpenClaw runtime config

OpenClaw supports custom OpenAI-compatible providers via `models.providers`.

Run:

```bash
openclaw config set models.mode merge

openclaw config set --json 'models.providers["nvidia-build"]' '{
  api: "openai-completions",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  apiKey: "${NVIDIA_API_KEY}",
  models: [
    { id: "moonshotai/kimi-k2-5", name: "Kimi K2.5 (NVIDIA Build)" }
  ]
}'
```

Notes:
- The NVIDIA docs commonly spell this model id as `moonshotai/kimi-k2-5`.
- This config only references `${NVIDIA_API_KEY}`; it does not store the key itself.

## 3) Set routing: OpenRouter primary, NVIDIA Build fallback

If OpenRouter has Kimi K2.5 configured:

```bash
openclaw models set openrouter/moonshotai/kimi-k2.5
openclaw models fallbacks add nvidia-build/moonshotai/kimi-k2-5
```

(Keep any other fallbacks you already rely on, e.g. Claude/Gemini.)

## 4) Verify

```bash
openclaw models status --probe
```

You should see both providers in the auth overview, and the resolved primary/fallback list.

## Security reminders

- `initData` / auth material should be treated as sensitive.
- Prefer `~/.openclaw/.env` or `openclaw models auth paste-token` flows over shell-only exports.
