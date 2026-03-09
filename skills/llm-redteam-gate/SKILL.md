---
name: llm-redteam-gate
description: CLI-first Promptfoo evaluation and red-team safety gate for ORION agent workflows.
metadata:
  invocation: user
---

# LLM Redteam Gate

Use this skill to run repeatable Promptfoo eval and red-team checks before merge/release, and fail fast when safety regressions cross agreed thresholds.

## 1) Purpose And When To Use

- Use before PR merge, release, or prompt/policy changes that could impact safety behavior.
- Use when adding new tools, memory pathways, MCP integrations, or policy-sensitive flows.
- Use when you need a deterministic CLI gate (not manual UI review).

## 2) Prereqs

- Node.js 18+.
- Provider credentials in env (example: `OPENAI_API_KEY`).
- Install Promptfoo (pick one):

```bash
# one-off (no install)
npx -y promptfoo@latest --version

# repo-local dev dependency
npm install --save-dev promptfoo
npx promptfoo --version

# global install
npm install -g promptfoo
promptfoo --version
```

- Optional for CI parsing:

```bash
brew install jq
```

## 3) Quick Onboarding (Copy + Run)

Starter config lives at `skills/llm-redteam-gate/examples/promptfooconfig.yaml`.

```bash
# Copy to repo root (default path used by helper)
cp skills/llm-redteam-gate/examples/promptfooconfig.yaml ./promptfooconfig.yaml

# Or copy to a custom location
cp skills/llm-redteam-gate/examples/promptfooconfig.yaml ./configs/promptfooconfig.yaml
```

```bash
bash skills/llm-redteam-gate/scripts/run_redteam_gate.sh -c promptfooconfig.yaml
```

## 4) Commands: Eval And Red-Team Runs

### One-command helper

```bash
bash skills/llm-redteam-gate/scripts/run_redteam_gate.sh
```

Examples:

```bash
# Use a non-default config and tighter redteam threshold
bash skills/llm-redteam-gate/scripts/run_redteam_gate.sh \
  --config configs/promptfooconfig.yaml \
  --max-redteam-fails 1

# Re-evaluate existing generated tests without re-running redteam generation
bash skills/llm-redteam-gate/scripts/run_redteam_gate.sh --skip-generate
```

```bash
# 1) Validate config before spending tokens
npx -y promptfoo@latest validate config -c promptfooconfig.yaml

# 2) Baseline eval
npx -y promptfoo@latest eval \
  -c promptfooconfig.yaml \
  -o .promptfoo/eval-results.json \
  --no-progress-bar

# 3) Red-team scan (generate + evaluate attacks)
npx -y promptfoo@latest redteam run \
  -c promptfooconfig.yaml \
  --output .promptfoo/redteam.yaml \
  --no-progress-bar

# 4) Re-evaluate from redteam config/tests and export machine-readable output
npx -y promptfoo@latest redteam eval \
  -c promptfooconfig.yaml \
  -o .promptfoo/redteam-results.json \
  --no-progress-bar
```

Note: First-time red-team usage may require Promptfoo email verification/auth before scans run.

## 5) CI Gate Example With Failure Thresholds

```bash
set -euo pipefail

MAX_EVAL_FAILS="${MAX_EVAL_FAILS:-0}"
MAX_REDTEAM_FAILS="${MAX_REDTEAM_FAILS:-2}"

npx -y promptfoo@latest eval -c promptfooconfig.yaml -o .promptfoo/eval-results.json --no-progress-bar
npx -y promptfoo@latest redteam eval -c promptfooconfig.yaml -o .promptfoo/redteam-results.json --no-progress-bar

eval_bad="$(jq '.results.stats.failures + .results.stats.errors' .promptfoo/eval-results.json)"
red_bad="$(jq '.results.stats.failures + .results.stats.errors' .promptfoo/redteam-results.json)"

echo "eval_bad=$eval_bad (max=$MAX_EVAL_FAILS)"
echo "redteam_bad=$red_bad (max=$MAX_REDTEAM_FAILS)"

test "$eval_bad" -le "$MAX_EVAL_FAILS"
test "$red_bad" -le "$MAX_REDTEAM_FAILS"
```

## 6) Output Interpretation And Next Actions

- `errors > 0`: infrastructure/provider issue first (credentials, rate limits, model outage, malformed config).
- `failures > threshold`: behavioral regression; block merge and triage failing cases by plugin/test input.
- Red-team failures in `prompt-extraction`, `pii:*`, or high-risk harmful categories: treat as release blocker.
- After fixes: rerun `eval` and `redteam eval`, compare counts, and store JSON artifacts for audit trail.
