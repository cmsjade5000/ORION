---
name: nano-banana-pro
description: Generate images via Gemini "Nano Banana Pro" and return a MEDIA: path for Telegram sending.
metadata:
  invocation: user
  openclaw:
    emoji: "🍌"
    # This skill supports file-backed secrets (recommended), so we do not
    # hard-require an env var. If no key is available at runtime, the skill
    # will error with a clear message.
---

# NOTE: Bundled Skill Exists

OpenClaw ships a bundled `nano-banana-pro` skill.

In production, ORION should prefer the **bundled** skill instructions at:
- `~/.npm-global/lib/node_modules/openclaw/skills/nano-banana-pro/SKILL.md`

This workspace copy exists only as a local fallback/reference. If you see a name collision,
assume the bundled skill is the source of truth.

# Nano Banana Pro (Workspace Fallback)

This skill generates an image via the Gemini API image-capable models and writes it to `tmp/`.

Output contract:
- On success, this skill returns a line like `MEDIA:/absolute/path/to/image.png`.
- The caller (ORION) should include that `MEDIA:` line in the final reply so OpenClaw delivers the image in Telegram.

## Setup (Local Secrets Only)

Provide the Gemini key via either:
- `GEMINI_API_KEY` environment variable, or
- `~/.openclaw/secrets/gemini.api_key` (recommended).

Permissions:

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
chmod 600 ~/.openclaw/secrets/gemini.api_key
```

## Example

```bash
node -e \"require('./skills/nano-banana-pro/manifest').generateImage({prompt:'A blueprint-style robot head icon, white ink on dark paper'})\"
```
