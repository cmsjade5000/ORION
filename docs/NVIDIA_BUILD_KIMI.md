# NVIDIA Build API (nvapi-...) + Kimi K2.5 (OpenClaw wiring)

Goal: keep ORION production lanes on **low-cost OpenRouter/local defaults**, while exposing **NVIDIA Build Kimi K2.5** as an intentional specialist lane instead of a noisy generic fallback.

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
  apiKey: {
    source: "env",
    provider: "default",
    id: "NVIDIA_API_KEY"
  },
  models: [
    { id: "moonshotai/kimi-k2.5", name: "Kimi K2.5 (NVIDIA Build)" }
  ]
}'
```

Notes:
- The NVIDIA docs currently spell this model id as `moonshotai/kimi-k2.5`.
- This config references `NVIDIA_API_KEY` via SecretRef; it does not store the key itself.

## 3) Set routing: keep production low-cost, reserve Kimi for a dedicated lane

Recommended posture:

```bash
openclaw models set openrouter/openrouter/free
openclaw models fallbacks add openai/gpt-oss-20b:free
```

Then pin Kimi only on an intentional specialist agent, for example `ember`, by setting:

```json
{
  "id": "ember",
  "model": {
    "primary": "openrouter/openrouter/free",
    "fallbacks": [
      "openai/gpt-oss-20b:free",
      "nvidia-build/moonshotai/kimi-k2.5"
    ]
  }
}
```

Recommended reliability knobs when NVIDIA Build is bursty:

```json
{
  "auth": {
    "cooldowns": {
      "failureWindowHours": 12,
      "overloadedProfileRotations": 0,
      "overloadedBackoffMs": 45000
    }
  }
}
```

Avoid putting Kimi in the default cron-heavy fallback chain for `main` and `ledger` if you are already seeing repeated `429` responses.

## 4) Verify

```bash
openclaw models status
```

You should see both providers in the auth overview, and the resolved primary/fallback list.

## Security reminders

- `initData` / auth material should be treated as sensitive.
- Prefer `~/.openclaw/.env` or `openclaw models auth paste-token` flows over shell-only exports.
