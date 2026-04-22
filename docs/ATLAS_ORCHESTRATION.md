# ATLAS Orchestration Conventions

This doc standardizes how ATLAS coordinates multi-step work so outputs remain:
- auditable (linked to Task Packets)
- resumable (state and retries are explicit)
- safe (stop gates preserved)

## When To Use

Use these conventions when ATLAS is coordinating:
- multiple specialists (NODE for packet/incident hygiene, PULSE for workflow queueing/retries, STRATUS for host implementation) for one outcome
- a parallel execution burst
- a sequence that may require retries/backoff
- a browser-led or local-device workflow that requires proof, approval handling, or host-side execution safety

## Required Artifacts

- A Task Packet in `tasks/INBOX/ATLAS.md` that links the work.
- If sub-agents are needed: Task Packets for each sub-agent in their inboxes.
- A final integrated `Result:` under the ATLAS packet that includes:
  - Status: OK|FAILED|PARTIAL
  - Findings: 3-10 bullets
  - Artifacts: file paths/log paths
  - Next step: one recommended action or `None`
- For direct-interaction workflows, also include a proof bundle summary:
  - Device Target
  - Action Class
  - Action Id or workflow id
  - approval state: `approved` | `not required` | `pending`
  - proof refs: screenshot, URL, structured result, or log path

## Parallel Execution (Preferred Shape)

1. ATLAS writes sub-agent Task Packets (NODE/PULSE/STRATUS) with:
   - `Requester: ATLAS`
   - narrow scope
   - explicit Success Criteria
   - explicit Stop Gates
   - NODE packets should focus on packet structure or incident records
   - PULSE packets should focus on queueing, retries, or bounded workflow pacing
   - STRATUS packets should focus on infra or host-side implementation
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

## Direct Interaction Rule

For direct device interaction, ATLAS must preserve the lane order from [docs/DEVICE_INTERACTION_POLICY.md](/Users/corystoner/Desktop/ORION/docs/DEVICE_INTERACTION_POLICY.md):
- managed browser first
- typed local-device actions second
- UI automation only as a last-mile fallback

If a packet skips to a broader or riskier lane without justification, ATLAS should stop and ask ORION to re-scope or approve the escalation.

For browser-led packets, ATLAS should:
- stage before submit when feasible
- capture URL and screenshot evidence
- return `pending verification` when proof is incomplete

For macOS node packets, ATLAS should:
- route typed host-side implementation details to STRATUS when needed
- reject packets that collapse into generic shell or arbitrary AppleScript execution
