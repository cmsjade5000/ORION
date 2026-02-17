# Cross-Agent Handoff Contracts

This document standardizes what information must be included when handing work between agents.

Goals:
- reduce back-and-forth questions
- keep outputs auditable and evidence-grounded
- prevent policy drift (single-bot, chain-of-command, safety)

## Retrieval To Drafting (WIRE -> SCRIBE)

Required inputs to SCRIBE:
- Destination: telegram | slack | email
- Audience: (default Cory)
- Time window used for retrieval
- Items with:
  - title
  - source name
  - url
  - published_at (timezone-aware)
  - one concrete claim per item

Rules:
- If the user asked for “latest/updates/news”, SCRIBE must not invent items without links.
- Use evidence validation via `scripts/evidence_check.py` when available.

## Drafting To Sending (SCRIBE -> ORION)

SCRIBE output must start with exactly one of:
- `TELEGRAM_MESSAGE:`
- `SLACK_MESSAGE:`
- `EMAIL_SUBJECT:` (then `EMAIL_BODY:`)
- `INTERNAL:`

ORION responsibilities before sending:
- sanity-check any time-sensitive claims and links
- respect single-bot policy and avoid leaking internal artifacts

Optional lint:
- `python3 scripts/scribe_lint.py --input draft.txt`
Optional scaffold + score:
- `python3 scripts/scribe_scaffold.py --destination telegram --input payload.json`
- `python3 scripts/scribe_score.py --input draft.txt`

## Discovery To Execution (PIXEL -> ORION -> ATLAS)

PIXEL should hand off:
- Idea
- Why now
- First 30-minute test
- Success signal
- Risks / stop conditions
- Owner handoff (who should execute next)

If a claim is time-sensitive:
- include links and timestamps
- prefer evidence validation first

## Crisis/Distress To Support/Ops (ORION -> EMBER -> ORION/ATLAS)

If user language indicates danger:
- ORION prioritizes safety guidance (US: 988) and hands to EMBER.

EMBER handoff back to ORION should include:
- triage label (red/yellow/green)
- recommended next step (reversible)
- any escalation triggers

If emergency bypass is used (ATLAS unavailable):
- include `Emergency: ATLAS_UNAVAILABLE` and `Incident: INC-...` in Task Packets
