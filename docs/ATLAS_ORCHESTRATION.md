# ATLAS Orchestration Conventions

This doc standardizes how ATLAS coordinates multi-step work so outputs remain:
- auditable (linked to Task Packets)
- resumable (state and retries are explicit)
- safe (stop gates preserved)

## When To Use

Use these conventions when ATLAS is coordinating:
- multiple specialists (NODE/PULSE/STRATUS) for one outcome
- a parallel execution burst
- a sequence that may require retries/backoff

## Required Artifacts

- A Task Packet in `tasks/INBOX/ATLAS.md` that links the work.
- If sub-agents are needed: Task Packets for each sub-agent in their inboxes.
- A final integrated `Result:` under the ATLAS packet that includes:
  - Status: OK|FAILED|PARTIAL
  - Findings: 3-10 bullets
  - Artifacts: file paths/log paths
  - Next step: one recommended action or `None`

## Parallel Execution (Preferred Shape)

1. ATLAS writes sub-agent Task Packets (NODE/PULSE/STRATUS) with:
   - `Requester: ATLAS`
   - narrow scope
   - explicit Success Criteria
   - explicit Stop Gates
2. ATLAS runs sub-agents in parallel when tasks do not depend on each other.
3. ATLAS merges results into one integrated response for ORION.

## Runner-Friendly Read-Only Packets

If a packet is safe and deterministic, it can be executed via `scripts/run_inbox_packets.py`.

Requirements:
- `Constraints:` must include `Read-only` or `Readonly`
- `Notify:` must include at least one of `telegram` or `discord`
- Must include `Commands to run:` with allowlisted commands (example: `- diagnose_gateway.sh`)

Optional retry controls:
- `Retry Max Attempts:` / `Retry Backoff Seconds:` / `Retry Backoff Multiplier:` / `Retry Max Backoff Seconds:`

## Failure Policy

- If a sub-agent fails: ATLAS reports partial results and a concrete next step.
- If an emergency bypass occurred (ORION direct to NODE/PULSE/STRATUS): ATLAS must produce a PIR.

