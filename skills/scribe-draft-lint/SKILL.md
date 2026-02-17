---
name: scribe-draft-lint
description: Lint SCRIBE drafts for output-contract compliance (header, emoji ban, email structure) and evidence-lock heuristics.
metadata:
  invocation: user
---

# SCRIBE Draft Lint

Use this skill to validate that SCRIBE draft text follows the strict output contract before ORION sends it.

## From File

```bash
python3 scripts/scribe_lint.py --input draft.txt
```

## From Stdin

```bash
cat draft.txt | python3 scripts/scribe_lint.py
```

## What It Checks

- first non-empty line is exactly one of:
  - `TELEGRAM_MESSAGE:`
  - `SLACK_MESSAGE:`
  - `EMAIL_SUBJECT:` (requires `EMAIL_BODY:`)
  - `INTERNAL:`
- no text before the header (except blank lines)
- emoji ban
- evidence-lock heuristic:
  - if the draft contains “news/update/latest” style language, require:
    - at least one URL
    - at least one evidence tag: `supported|inferred|needs-source`

