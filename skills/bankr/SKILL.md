---
name: bankr
description: Read-only on-chain info via Bankr CLI (balances, holdings, portfolio questions). Write intents are blocked by default.
metadata:
  invocation: user
  openclaw:
    emoji: "🏦"
---

# Bankr (Read-Only By Default)

This workspace integrates with the Bankr CLI for on-chain questions (balances, holdings, portfolio info).

## Safety Contract

- Default posture is **read-only**.
- Any prompt that looks like it could **move funds** or **create/sign/submit transactions** is **blocked** by default.
- Only allow write intents with explicit user confirmation and `--allow-write`.

## Setup (Local)

1. Install CLI:

```bash
npm install -g @bankr/cli
```

2. Authenticate:

```bash
bankr login
```

If you see “Agent API access is not enabled”, enable Agent API access for your key at the Bankr dashboard, then re-login.

## Usage

Read-only prompt:

```bash
python3 scripts/bankr_prompt.py "What is my ETH balance on Base?"
```

If the prompt takes too long, the wrapper times out (default 180s). If Bankr printed a Job ID, you can poll it:

```bash
bankr status <jobId>
```

Allow write intent (only after explicit confirmation):

```bash
python3 scripts/bankr_prompt.py --allow-write "Swap 0.01 ETH to USDC on Base"
```

## Troubleshooting

- Check auth:
```bash
bankr whoami
```

- See available Bankr skills:
```bash
bankr skills
```
