# Bankr Integration (CLI)

This repo supports using the Bankr CLI for on-chain questions (balances, holdings, portfolio status).

## Security / Safety Defaults

- Treat Bankr as **capable of write actions** (signing/submitting transactions).
- Default posture in this repo is **read-only**.
- Use the safe wrapper `scripts/bankr_prompt.py` which blocks write intents by default.
- Only allow write intents after explicit user confirmation.

## Setup (Local Machine Only)

Install:

```bash
npm install -g @bankr/cli
```

Login:

```bash
bankr login
```

If the CLI reports that **Agent API access** is not enabled for your key, enable it in the Bankr dashboard and re-run `bankr login`.

## Usage

Read-only prompt:

```bash
python3 scripts/bankr_prompt.py "What is my ETH balance on Base?"
```

If the prompt takes too long, the wrapper times out (default 180s). If Bankr printed a Job ID, you can poll it:

```bash
bankr status <jobId>
```

Write intent (only with explicit confirmation):

```bash
python3 scripts/bankr_prompt.py --allow-write "Swap 0.01 ETH to USDC on Base"
```

Raw CLI utilities:

```bash
bankr whoami
bankr skills
```

## Notes

- Do not commit any Bankr config or credentials. Bankr stores credentials under `~/.bankr/` by default.
