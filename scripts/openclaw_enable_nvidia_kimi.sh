#!/usr/bin/env bash
set -euo pipefail

# This script wires NVIDIA Build (nvapi-...) as a custom OpenClaw provider.
# It does NOT change your primary model by default.
#
# IMPORTANT:
# - Do NOT put secrets in this repo.
# - Put NVIDIA_API_KEY in ~/.openclaw/.env (chmod 600) before running.
#
# Safe: only modifies ~/.openclaw/openclaw.json via `openclaw config set`.

openclaw config set models.mode merge

openclaw config set --json 'models.providers["nvidia-build"]' '{
  api: "openai-completions",
  baseUrl: "https://integrate.api.nvidia.com/v1",
  apiKey: "${NVIDIA_API_KEY}",
  models: [
    { id: "moonshotai/kimi-k2-5", name: "Kimi K2.5 (NVIDIA Build)" }
  ]
}'

# Optional: add NVIDIA Build as a fallback for when you *do* pick an OpenRouter Kimi primary.
# openclaw models fallbacks add nvidia-build/moonshotai/kimi-k2-5

# Optional: switch primary model to OpenRouter Kimi K2.5.
# openclaw models set openrouter/moonshotai/kimi-k2.5

openclaw models status --probe
