# The Keep

## What the Keep Is
The Keep is the set of local-only secret files and credential material needed to run Gateway.

It includes:
- API keys (OpenRouter, Gemini, etc.)
- Bot tokens (Telegram)
- OAuth refresh tokens / auth profiles
- Service credentials (email, Slack if ever re-enabled)

It does not include:
- Normal configuration (model names, routing, allowlists)
- Generated agent artifacts (`agents/*/SOUL.md`)
- Anything safe to commit to Git

## Where Secrets Live
Primary locations (local machine only):
- `~/.config/clawdbot/secrets/` (token files like Telegram)
- `~/.openclaw/.env` (provider keys used by OpenClaw)
- `~/.openclaw/agents/main/agent/auth-profiles.json` (OAuth/token profiles; treat as secret)

Rules:
- Never commit these paths to Git.
- Ensure permissions are tight (`chmod 600` for secret files).
- Prefer Keychain/launchd-secured environment injection if/when we harden further.

## Naming & Structure
- Token files should contain only the token value and a trailing newline.
- Use clear filenames: `telegram.token`, `openrouter.key`, etc.
- When rotating, keep the old value nowhere except the provider's revocation history.

## Access Model
- Cory is the only authorized operator for secrets.
- Agents may request that Cory provides or rotates credentials, but should not ask to paste secrets into chat.
- Any operation that writes credential material to disk requires explicit confirmation by Cory.

## Rotation & Revocation
Rotate immediately if:
- A secret was pasted into chat.
- A secret appeared in terminal output/logs.
- A token file permissions were too broad.

When rotating:
1. Revoke at provider.
2. Replace local secret material.
3. Restart the gateway.
4. Run a quick functional check (Telegram ping, model auth status).

## What Never Goes in the Keep
- Secrets in repository files (including `openclaw.yaml`).
- Secrets in generated artifacts (`agents/*/SOUL.md`).
- Secrets embedded in documentation examples.
