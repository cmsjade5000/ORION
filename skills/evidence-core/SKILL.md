---
name: evidence-core
description: Validate evidence items (source tier + freshness window + claim-to-link traceability) for WIRE/SCRIBE/ORION outputs.
metadata:
  invocation: user
---

# Evidence Core

Use this skill to validate that “latest/updates” items are:
- time-bounded (freshness window)
- tiered by source credibility
- claim-to-link traceable

## Input Format

Provide JSON with an `items` array. Each item must include:
- `title` (string)
- `source` (string)
- `url` (string)
- `published_at` (RFC3339/ISO8601, must include timezone; `Z` allowed)
- `claim` (string; one concrete claim attributable to the link)
- `source_tier` one of: `primary` | `secondary` | `low`
- `confidence` one of: `high` | `medium` | `low`

Optional top-level:
- `time_window_hours` (number, default 24)

## Validate From File

```bash
python3 scripts/evidence_check.py --input evidence.json
```

## Validate From Stdin

```bash
cat evidence.json | python3 scripts/evidence_check.py
```

## Tighten Window / Tier

```bash
python3 scripts/evidence_check.py --input evidence.json --time-window-hours 12 --min-source-tier secondary
```

