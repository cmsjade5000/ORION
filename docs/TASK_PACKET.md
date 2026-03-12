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
- Do not pre-create an empty `Result:` placeholder. Leave the `Result:` block for the specialist/runner.
- If the packet included `Notify: telegram`, ORION may notify Cory automatically (see `scripts/notify_inbox_results.py` + `HEARTBEAT.md`).
- For allowlisted read-only packets, `scripts/run_inbox_packets.py` can execute the `Commands to run:` section and write the `Result:` block.
  - Formatting requirement for `Commands to run:`:
    - Preferred: header line `Commands to run:` followed by bullet lines (example `- diagnose_gateway.sh`).
    - Supported: single-line form `Commands to run: diagnose_gateway.sh`.
- Requester field policy:
  - Most specialist inboxes: `Requester: ORION`.
  - POLARIS inbox: `Requester: ORION`.
  - ATLAS-directed sub-agents (`NODE`, `PULSE`, `STRATUS`): `Requester: ATLAS` (or `Requester: ORION` only with `Emergency: ATLAS_UNAVAILABLE`).

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
