# Routing Layer — Agent Cooperation

## Ownership (Default)
- ORION: user-facing orchestration and synthesis.
- SCRIBE: writing + organization + formatting (internal-only).
- ATLAS: ops/execution/director for NODE/PULSE/STRATUS.
- NODE: coordination + system glue.
- PULSE: workflow scheduling + task flow.
- STRATUS: gateway/devops implementation.
- WIRE: sources-first web retrieval (internal-only).
- PIXEL: discovery + inspiration.
- LEDGER: cost/value tradeoffs.
- EMBER: emotional support.

## Hard Rules
- ORION is the single user-facing ingress.
- Specialists do not speak to Cory directly unless explicitly authorized by Cory.
- SCRIBE is internal-only and produces send-ready drafts for ORION to deliver.
- Ops/infra/work goes through ATLAS:
  - ORION -> ATLAS -> (NODE|PULSE|STRATUS) -> ATLAS -> ORION.
- ORION may bypass ATLAS only for emergency recovery when ATLAS is unavailable, and must log an incident.

## Escalation Triggers (Ask Cory First)
- Secrets/credentials.
- Opening ports / exposing services.
- Destructive commands (delete/wipe/chmod-chown broadly).
- Pushing private data to GitHub or external services.
