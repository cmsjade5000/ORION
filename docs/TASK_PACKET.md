# Task Packet Spec

This document defines the canonical **Task Packet** format used for:

- Cron payloads (OpenClaw `agentTurn` messages)
- ORION → specialist delegation (sessions/swarm)
- ORION → per-agent inbox assignment (`tasks/INBOX/*.md`)

Goal: keep delegation structured, auditable, and low-ambiguity.

## Rules

- ORION must include a Task Packet for any non-trivial delegation.
- Cron jobs must use a Task Packet in the `--message` payload.
- Specialists should refuse work that lacks enough fields to execute safely.
- Native subagent control for active sessions may update packet status or notes, but the Task Packet remains the durable source of intent and guardrails.

## Minimal Task Packet (Required Fields)

Use this exact header + list format:

```text
TASK_PACKET v1
Owner: <AGENT>          # who executes (ATLAS/NODE/POLARIS/etc)
Requester: <ORION|ATLAS>
Objective: <one sentence outcome>
Success Criteria:
- <verifiable check 1>
Constraints:
- <must/never rules>
Inputs:
- <paths/links/snippets>
Risks:
- <risk + mitigation or "low">
Stop Gates:
- <what requires Cory approval>
Output Format:
- <diff/checklist/report/commands>
```

## Optional Fields (Use When Helpful)

- `Context:` short background paragraph
- For transcript-aware runtimes, keep `Context:` to net-new facts, status, and artifact refs; do not paste the full prior transcript when the runtime already injects it.
- `Scope:` included/excluded
- `Timebox:` e.g., `30m` or `2h`
- `Execution Mode:` `direct` | `delegate` | `parallel` | `batch`
  - `parallel` is for independent, non-destructive work only.
  - `batch` is for bounded row-wise jobs (for example `spawn_agents_on_csv`) with explicit schema and limits.
- `Lifecycle State:` `spawned` | `yielded` | `steered` | `cancelled` | `completed`
  - Use when a packet is mirrored into status notes or delegated-job tracking.
  - `yielded` means the current turn was suspended with `sessions_yield`; it does not replace the Task Packet as the durable record.
- `Policy Mode:` `audit` | `block`
  - Optional runtime enforcement hint for automation packets that pass through ORION policy gating.
  - Default is `audit`; use `block` only after clean-window promotion gates are satisfied.
- `Tool Scope:` `read-only` | `write`
- `Tool Plan:` compact list of intended tool families (for example `mcp-read`, `parallel-checks`, `subagents`)
- `Retrieval Order:` `mcp-first` | `web-first`
  - Default to `mcp-first` when relevant resources exist.
- `Evidence Required:` required proof items (paths/outputs/check lines) before marking complete.
- `Rollback:` required for write or destructive flows; document reversible fallback.
- `Dependencies:` other tasks/agents needed first
- `Checkpoints:` interim status points
- `Notify:` `telegram` | `discord` | `none` (also supports `telegram,discord`)
  - Use `Notify: telegram` when a delegated packet is user-initiated and Cory expects a follow-up message when the specialist posts a `Result:`.
  - If the packet will execute via the inbox runner, use `Notify: telegram` so Cory gets:
    - a one-time "Queued" update, and
    - a follow-up "Results" update when `Result:` is written.
- `Idempotency Key:` optional stable key to dedupe runner-backed packets across retries/reruns.
  - Used by `scripts/run_inbox_packets.py` to avoid repeating the same work when the packet is re-filed or re-queued.
- `Packet ID:` optional stable packet identity. If omitted, automation derives one from packet content or idempotency.
- `Parent Packet ID:` optional lineage pointer for follow-on or recovery packets.
- `Root Packet ID:` optional root lineage pointer across multi-hop workflows.
- `Workflow ID:` optional workflow identity for grouping related packets and job artifacts.
- `Routing Override Rationale:` required when a packet intentionally assigns an owner that differs from the deterministic routing contract.
- Retry policy (used by `scripts/run_inbox_packets.py` for allowlisted read-only packets):
  - `Retry Max Attempts:` integer (default `1`, meaning no retries)
  - `Retry Backoff Seconds:` number (default `60`)
  - `Retry Backoff Multiplier:` number (default `2`)
  - `Retry Max Backoff Seconds:` number (default `3600`)
- `Severity:` `P0` (emergency) | `P1` (urgent) | `P2` (normal) | `P3` (backlog)
- `Emergency:` use only for explicit emergency modes (example: `ATLAS_UNAVAILABLE`)
- `Incident:` incident id when an emergency bypass is used (see `tasks/INCIDENTS.md`)
- `Opened:` `YYYY-MM-DD` packet open date (required for POLARIS inbox packets)
- `Due:` `YYYY-MM-DD` target completion date (required for POLARIS inbox packets)
- `Approval Gate:` optional explicit policy gate (example: `LEDGER_RESULT_REQUIRED`)
- `Gate Evidence:` short pointer to the gating result/source (example: `tasks/INBOX/LEDGER.md packet@line ...`)
- Device-control fields when relevant:
  - `Device Target:` for example `managed-browser`, `personal-browser`, `macos-node`
  - `Action Class:` for example `read_like`, `local_write`, `identity_bearing`, `destructive`, `persistent_change`
  - `Action Id:` typed action identifier such as `open_app`, `open_url`, `shortcut`
  - `Inputs Summary:` concise parameter summary safe to log/review

## Cron Payload Guidance

Cron jobs are blind execution. Keep cron packets:

- bounded (timebox + narrow scope)
- non-destructive by default
- `deliver=false` unless Cory explicitly wants messages

Example cron `--message` payload (inline):

```text
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Run heartbeat once and update tasks/QUEUE.md if needed.
Success Criteria:
- Returns HEARTBEAT_OK when idle.
- Updates tasks/QUEUE.md only when there is a clear Ready item.
Constraints:
- Do not browse endlessly.
- Do not message Telegram unless explicitly asked in the task.
Inputs:
- HEARTBEAT.md
- tasks/QUEUE.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any credential change.
Output Format:
- Short checklist of what was checked + what changed.
```

Suggested additions for tool-heavy cron packets:
- `Execution Mode: direct`
- `Tool Scope: read-only` unless explicitly approved otherwise
- `Evidence Required:` command output path or report path
- `Rollback:` if packet can write or modify system state
- For any device-interaction prep packet, prefer queue/stage semantics over direct side effects unless prior approval is explicit

## Device-Control Packet Shape

For browser-led or local-device workflows, prefer adding these fields:

```text
Device Target: managed-browser | personal-browser | macos-node
Action Class: read_like | local_write | identity_bearing | destructive | persistent_change
Action Id: <typed action or workflow id>
Inputs Summary:
- <safe-to-log parameter summary>
Evidence Required:
- <artifact or screenshot path>
- <structured result or check line>
Rollback:
- <reversible fallback or "none">
```

Guidance:
- `Device Target: managed-browser` is the default when browser automation is sufficient.
- `Device Target: personal-browser` should be explicit and treated as higher trust/risk.
- `Device Target: macos-node` should point to a typed action from [docs/MACOS_NODE_ACTION_MODEL.md](/Users/corystoner/Desktop/ORION/docs/MACOS_NODE_ACTION_MODEL.md).
- `Action Class:` should match the approval class, not the user intent.
- `Inputs Summary:` must be review-safe and should not echo secrets or full sensitive payloads.

## Device-Control Examples

### Example: Browser-Led Review Packet

```text
TASK_PACKET v1
Owner: ATLAS
Requester: ORION
Objective: Open the expense portal, navigate to the pending report, and stage the draft for Cory's approval.
Execution Mode: delegate
Tool Scope: write
Device Target: managed-browser
Action Class: identity_bearing
Action Id: expense_report_stage
Inputs Summary:
- expense portal
- pending March report
Success Criteria:
- Draft is opened and staged for review.
- No submission occurs.
Constraints:
- Managed browser only.
- Do not submit, send, or approve the report.
Inputs:
- docs/operator-packs/expense-report.md
Risks:
- Acts inside Cory's authenticated session; mitigate by staging only and capturing proof.
Stop Gates:
- Any submit, send, payment, or account-setting change.
Evidence Required:
- Screenshot of staged draft.
- Portal URL for the staged page.
- Final action summary.
Rollback:
- Close draft without submitting.
Output Format:
- Short checklist + proof bundle paths.
```

### Example: Typed macOS Node Packet

```text
TASK_PACKET v1
Owner: ATLAS
Requester: ORION
Objective: Open Notes and reveal the meeting-prep folder for review.
Execution Mode: delegate
Tool Scope: write
Device Target: macos-node
Action Class: local_write
Action Id: open_app
Inputs Summary:
- Notes.app
- meeting-prep folder reveal
Success Criteria:
- Notes is opened.
- Target folder is visible for Cory.
Constraints:
- Use typed actions only.
- No arbitrary shell execution.
Inputs:
- docs/MACOS_NODE_ACTION_MODEL.md
Risks:
- Low local UI side effect; mitigate with typed action and proof.
Stop Gates:
- Any request to modify note contents without explicit approval.
Evidence Required:
- Structured action result.
- Timestamp.
- Optional screenshot if part of a visible workflow.
Rollback:
- None.
Output Format:
- Structured result + proof summary.
```

## ORION → Specialist Session Guidance

For internal sessions, include:

- Specialist SOUL: `agents/<AGENT>/SOUL.md`
- Policy anchors: `SECURITY.md`, `TOOLS.md`, `USER.md`
- Task Packet (in-message or as a file link)
- If the runtime already carries realtime transcript context, include only the delta needed for safe execution plus any artifact paths that are not already obvious from the thread.

## Per-Agent Inbox Guidance

Inbox files are append-only queues of Task Packets.

- ORION assigns by appending a new Task Packet to `tasks/INBOX/<AGENT>.md`.
- Specialist marks completion by adding a short `Result:` block under the packet.
- Terminal result states are `OK`, `FAILED`, `BLOCKED`, and `CANCELLED`.
  - `OK` means the requested work is complete or ready for the next verification lane.
  - `FAILED` means execution was attempted and did not succeed.
  - `BLOCKED` means work cannot proceed without a concrete external input or approval.
  - `CANCELLED` means the packet is intentionally closed because the source task became obsolete or terminal.
- Packet appenders must enforce duplicate suppression before writing:
  - compare `Idempotency Key` first,
  - then `Packet ID`,
  - then the pre-`Result:` content hash.
  Matching packets must not be appended again, whether the existing copy is active or terminal.
- Follow-on, recovery, and triage packets must carry lineage (`Parent Packet ID`, `Root Packet ID`, and `Workflow ID`) when generated automatically.
- When a source/root packet becomes terminal, generated recovery or triage descendants should be terminalized with `Status: CANCELLED` and `Reason: superseded_by_terminal_source` instead of lingering as active queue work.
- Packet owner selection is decision-driven: validate the objective/input against `src/core/shared/orion_routing_contract.json` and `docs/AGENT_OWNERSHIP_MATRIX.md`; use `Routing Override Rationale:` when intentionally assigning a different owner.
- Do not pre-create an empty `Result:` placeholder. Leave the `Result:` block for the specialist/runner.
- If the packet included `Notify: telegram`, ORION may notify Cory automatically for result/workflow milestones (see `scripts/notify_inbox_results.py` + `HEARTBEAT.md`).
- For allowlisted read-only packets, `scripts/run_inbox_packets.py` can execute the `Commands to run:` section and write the `Result:` block.
- `scripts/task_execution_loop.py` and `scripts/inbox_cycle.py` also derive durable delegated-job state under `tasks/JOBS/*.json`.
- `tasks/JOBS/summary.json` includes `notification_delivery`, which shows whether a queued/result notification is delivered, failed, suppressed, pending, or not requested.
- Completed packets remain in the active inbox during the notification age-out window. `scripts/archive_completed_inbox_packets.py --apply` moves only terminal, successfully summarized packets older than the configured threshold into `tasks/INBOX/archive/`; queued, stale, blocked, and pending-verification packets stay active.
  - Formatting requirement for `Commands to run:`:
    - Preferred: header line `Commands to run:` followed by bullet lines (example `- diagnose_gateway.sh`).
    - Supported: single-line form `Commands to run: diagnose_gateway.sh`.
- For tested automatic handoff, a terminal packet may declare one explicit follow-on packet using the prefixed mirror contract:
  - `Next Packet On Result:` `OK` | `FAILED` | `BLOCKED` | `ANY` (optional; default `OK`)
  - `Next Packet Owner:`
  - `Next Packet Requester:`
  - `Next Packet Objective:`
  - `Next Packet Success Criteria:`
  - `Next Packet Constraints:`
  - `Next Packet Inputs:`
  - `Next Packet Risks:`
  - `Next Packet Stop Gates:`
  - `Next Packet Output Format:`
  - Optional extra follow-on fields may also be supplied with the same prefix, for example `Next Packet Notify:` or `Next Packet Tool Scope:`.
  - `scripts/task_execution_loop.py` appends that follow-on packet exactly once and records `Handoff Source: <inbox>:<line>` in the generated packet.
  - Generated follow-on packets also carry `Packet ID`, `Parent Packet ID`, `Root Packet ID`, and `Workflow ID` so durable job artifacts can group the whole workflow instead of isolated packets.
- When a pending packet exceeds the stale threshold, `scripts/task_execution_loop.py --apply` may append one recovery packet exactly once with a `recovery:stale:` idempotency key and preserved workflow lineage.
- Requester field policy:
  - Most specialist inboxes: `Requester: ORION`.
  - POLARIS inbox: `Requester: ORION`.
  - ATLAS-directed sub-agents (`NODE`, `PULSE`, `STRATUS`): `Requester: ATLAS` (or `Requester: ORION` only with `Emergency: ATLAS_UNAVAILABLE`).

Device-control routing guidance:
- Browser-led direct interaction packets should default to `Owner: ATLAS`.
- Local device-node execution packets should default to `Owner: ATLAS`, with ATLAS routing host-side implementation work to STRATUS when needed.
- Scheduled prep or approval-queue packets may use `Owner: PULSE` only when the packet is bounded, retry-safe, and does not perform approval-gated side effects on its own.

### POLARIS Admin Packets

For admin-copilot workflows, POLARIS packets should also include:
- `Notify: telegram`
- `Opened: YYYY-MM-DD`
- `Due: YYYY-MM-DD`
- `Execution Mode: direct|delegate`
- `Tool Scope: read-only|write`

Default posture:
- prepare/draft first
- no external side effects without explicit approval relayed by ORION

## Kalshi Risk-Gated Change Packets

For Kalshi policy/risk/parameter changes:
- Obtain LEDGER analysis first.
- Include `Approval Gate: LEDGER_RESULT_REQUIRED`.
- Include `Gate Evidence:` pointing to the LEDGER `Result:` location.
- Only then route execution packets through ATLAS.

Validation rules:
- `Approval Gate` must be one of the allowlisted values.
- When `Approval Gate` is present, `Gate Evidence` is required.
- For `Approval Gate: LEDGER_RESULT_REQUIRED`, packet `Owner` must be `ATLAS` or `ORION`, and `Gate Evidence` must reference `LEDGER`.

## Validation (Recommended)

Validate inbox packets stay structured:

```bash
python3 scripts/validate_task_packets.py
```
