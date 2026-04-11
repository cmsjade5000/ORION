# Promptfoo Gate

This repo now has an ORION-specific Promptfoo config at:

- `config/promptfoo/orion-safety-gate.yaml`

The config is intentionally focused on the highest-risk ORION behaviors:

- false completion claims for operational work
- cron and reminder delegation discipline
- spending-decision intake before LEDGER handoff
- destructive-reset confirmation gates
- crisis-language safety handling
- prompt extraction and secret exfiltration refusal

## Why This Uses OpenAI

ORION's live runtime is now OpenAI-first, with OpenRouter retained only as an explicit compatibility fallback lane.

Relevant references:

- `docs/LLM_ACCESS.md`
- `.github/workflows/ci.yml`
- `skills/llm-redteam-gate/SKILL.md`

That means Promptfoo can run as a stable evaluation layer without changing the production routing posture.

## Commands

Validate config only:

```bash
make redteam-validate
```

Run eval + redteam gate:

```bash
make redteam-gate
```

Override the config path if needed:

```bash
make redteam-validate PROMPTFOO_CONFIG=config/promptfoo/orion-safety-gate.yaml
make redteam-gate PROMPTFOO_CONFIG=config/promptfoo/orion-safety-gate.yaml
```

Outputs are written to:

- `.promptfoo/eval-results.json`
- `.promptfoo/redteam.yaml`
- `.promptfoo/redteam-results.json`

## Scope Notes

- This is a guardrail scaffold, not a full ORION behavioral test suite.
- It complements the existing routing simulations in `eval/` and the `llm-redteam-gate` skill.
- If Promptfoo proves useful, the next step should be expanding the test set with repo-specific Task Packet, routing, and evidence-handling cases rather than adding more providers first.
