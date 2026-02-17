---
name: scribe-draft-tools
description: Generate contract-compliant SCRIBE scaffolds and score drafts for quality (complements scribe-draft-lint).
metadata:
  invocation: user
---

# SCRIBE Draft Tools

This skill provides two deterministic helpers:
- scaffold generation (contract-compliant starting structure)
- quality scoring (quick triage for ORION)

## Scaffold

Input JSON example:

```json
{
  "goal": "Summarize what changed this week.",
  "tone": "calm, pragmatic",
  "must_include": ["one-line status", "next step"],
  "must_not_include": ["speculation"],
  "evidence_items": [
    {"title": "Release notes", "url": "https://example.com", "tag": "supported"}
  ]
}
```

Generate:

```bash
python3 scripts/scribe_scaffold.py --destination telegram --input payload.json
```

## Score A Draft

```bash
python3 scripts/scribe_score.py --input draft.txt
```

Exit code is `0` if score >= 70, else `1`.

