---
name: secrets-scan
description: Scan the repo for leaked secrets before commit/push (OpenRouter/Gemini/Telegram/etc). Use before publishing changes.
metadata:
  invocation: user
---

# Secrets Scan (Pre-Commit)

Goal: catch accidental secrets before they hit Git history.

## What To Scan For

- API keys and tokens (Telegram, OpenRouter, Google, Slack, etc.)
- `.env` and token files
- OAuth caches / auth profiles

## Quick Scan (Fast)

Run from repo root:

```bash
rg -n -S -P "(sk-or-v1-[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{20,}|xoxb-[A-Za-z0-9-]{10,}|xapp-[A-Za-z0-9-]{10,}|mm_live_[A-Za-z0-9]+|\\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\\b)" .
```

If anything matches, stop and fix before committing.

## Full Scan (Recommended)

If `gitleaks` is installed:

```bash
gitleaks detect --source . --no-git --redact
gitleaks detect --source . --redact
```

If `gitleaks` is not installed, install manually (preferred on macOS):

```bash
brew install gitleaks
```

## Response If A Secret Is Found

1. Remove the secret from the repo immediately.
2. If it was committed/pushed, rotate the secret at the provider.
3. Add/confirm an ignore rule in `.gitignore` for local-only secret paths.
