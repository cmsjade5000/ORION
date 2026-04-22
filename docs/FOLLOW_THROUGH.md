# Follow-Through (Stop Needing "Continue")

Problem: ORION can delegate multi-step work to specialists, but results may land asynchronously (for example in `tasks/INBOX/*.md`). If nothing triggers a user-facing follow-up, Cory ends up prodding ORION with “continue” messages.

Goal: when a delegated packet is queued or completes, the inbox cycle advances what it can, reconciles ticket state, records durable job state, and sends a short Telegram or Discord update automatically.

Inbound email uses a separate lightweight triage loop first: AgentMail is polled, safe messages are converted into `TASK_PACKET v1` entries, and then the normal inbox cycle picks those packets up.

For the admin-copilot posture, this is required infrastructure rather than optional polish.

Canonical runtime model:
- `tasks/INBOX/*.md` remains the durable input surface for packet creation, result append, and lineage.
- `tasks/JOBS/<job>.json`, `tasks/JOBS/wf-*.json`, and `tasks/JOBS/summary.json` are the canonical read model for delegated-work state.
- Notification and operator-status surfaces should read `tasks/JOBS` artifacts first and treat inbox markdown as compatibility fallback only.

## Mechanism (Single-Bot Mode)

1. ORION creates a Task Packet in `tasks/INBOX/<AGENT>.md` and includes:
   - `Notify: telegram` or `Notify: discord` (or `Notify: telegram,discord`)
2. The specialist writes a `Result:` block under that packet when done.
3. A periodic inbox cycle executes:
   - `python3 scripts/run_inbox_packets.py --repo-root .`
   - `python3 scripts/task_execution_loop.py --repo-root . --apply`
   - `python3 scripts/notify_inbox_results.py --repo-root . --require-notify-telegram --notify-queued`
   - Convenience wrapper: `python3 scripts/inbox_cycle.py --repo-root .`
   - Optional policy gate hardening for the notifier:
     - `--policy-rules config/orion_policy_rules.json`
     - `--policy-mode audit|block` (default `audit`)
4. The cycle writes durable per-job artifacts to `tasks/JOBS/*.json`, per-workflow artifacts to `tasks/JOBS/wf-*.json`, updates `tasks/JOBS/summary.json`, and the notifier remembers what it already sent (state in `tmp/inbox_notify_state.json`).

Read-model expectations:
- Per-job artifacts carry the canonical state, state reason, notify channels, stable queued/result digests, and a safe result preview.
- `summary.json` is the aggregate API for queued/result/workflow status; status views should not re-infer that state from inbox markdown when the summary is present.

Canonical delegated-job states:
- `queued`
- `in_progress`
- `pending_verification`
- `blocked`
- `complete`

## Next Packet Contract

If one delegated step should automatically hand off to the next specialist, add a prefixed follow-on packet to the parent packet:

```text
Next Packet On Result: OK
Next Packet Owner: NODE
Next Packet Requester: ATLAS
Next Packet Objective: Continue the second stage.
Next Packet Success Criteria:
- Continue the work.
Next Packet Constraints:
- Read-only.
Next Packet Inputs:
- tasks/WORK/testing/0004-handoff.md
Next Packet Risks:
- low
Next Packet Stop Gates:
- Any destructive command.
Next Packet Output Format:
- Short checklist.
```

Rules:
- The follow-on packet is validated like a normal packet.
- `task_execution_loop.py --apply` appends it exactly once after the parent packet reaches the matching terminal result.
- The generated follow-on packet includes `Handoff Source: <inbox>:<line>` for auditability and dedupe.
- Generated follow-ons also inherit workflow lineage through `Packet ID`, `Parent Packet ID`, `Root Packet ID`, and `Workflow ID`.
- If a pending packet goes stale, the same reconcile pass can append one recovery packet with preserved lineage so the workflow does not just sit in notes forever.

Notes:
- The notifier is bounded and non-spammy (default max 3 results per run).
- Heartbeat outputs remain `NO_REPLY`; the script does the send.
  - Telegram: direct API call (token file or env var).
  - Discord: uses `openclaw message send --channel discord ...` (so this script never touches the Discord token).
- Telegram and Discord should share one normalized delegated-job event model, with only delivery adapters differing.

## Closed-Loop Enforcement

To prevent packet/ticket drift, run:

- `python3 scripts/task_execution_loop.py --apply`
  - Reconciles safe lane/state drift:
    - pending packet + referenced ticket -> `in-progress`
    - terminal packet result + referenced ticket -> `testing`
    - lane/status mismatch -> rewrites `Status:` to lane-derived value
  - Regenerates `tasks/NOTES/status.md` and `tasks/NOTES/plan.md`
- `python3 scripts/task_execution_loop.py --apply --strict-stale --stale-hours 24`
  - Same reconcile behavior, but exits non-zero if pending packets exceed stale threshold.
  - Intended for heartbeat/cron stop-gate style enforcement.
  - In non-strict apply mode, stale packets also get an exact-once recovery handoff to `ATLAS` or `ORION` depending on ownership.

## Milestone-Only Updates (POLARIS Rollouts)

For POLARIS/admin rollout work, prefer milestone updates over step-by-step chatter.

Recommended milestone labels:
- `Scaffold complete`
- `Routing + gates complete`
- `Tests green + config active`

Guidelines:
- Use `Notify: telegram` on the relevant Task Packets.
- Keep messages one to three short bullets.
- Do not emit high-frequency progress pings between milestones.

Weekly routing audit cadence:
- ORION runs a weekly routing audit from `/Users/corystoner/src/ORION`.
- Audit/report format is defined in `tasks/INBOX/POLARIS.md` and policy ownership in `docs/AGENT_OWNERSHIP_MATRIX.md`.

## Recommended Packet Result Format

Specialists should add, under the packet:

```text
Result:
- Status: OK | FAILED | BLOCKED
- What changed / what I found:
- Next step (if any):
```

Keep it short; avoid tool logs and secrets.

## Cron (Compatibility Only)

Do not use OpenClaw `agentTurn` cron wrappers for deterministic ORION maintenance by default.
The compatibility installer now requires an explicit override:

```bash
ALLOW_LLM_CRON_WRAPPERS=1 bash scripts/install_orion_assistant_crons.sh --apply
```

For local unattended execution on macOS, prefer:

```bash
bash scripts/install_orion_local_maintenance_launchagents.sh
```

`install_orion_local_job_bundle_launchagent.sh` now exists only as a compatibility wrapper that removes the legacy bundle LaunchAgent and forwards to the canonical maintenance installer.

The maintenance bundle now treats `assistant-inbox-notify` running `scripts/inbox_cycle.py` as the canonical core follow-through loop. Keep `task_execution_loop.py` available for operator diagnostics and manual reconcile, but do not install a second overlapping scheduled task loop in ORION core.

Nightly reliability review:

- `python3 scripts/orion_error_db.py review --window-hours 24 --apply-safe-fixes --escalate-incidents --json`
- Report artifact: `tasks/NOTES/error-review.md`
- Deliberate session maintenance: `AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json`
- Report artifact: `tasks/NOTES/session-maintenance.md`
- Incident bundle snapshot: `python3 scripts/orion_incident_bundle.py --repo-root . --write-latest --json`
- Report artifact: `tasks/NOTES/orion-ops-status.md`

Equivalent manual `agentTurn` cron commands are kept only for explicit compatibility/debug cases:

```bash
openclaw cron add \
  --name "assistant-email-triage" \
  --description "Poll ORION AgentMail and route safe inbound email into inbox task packets" \
  --cron "*/5 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --wake next-heartbeat \
  --message "Use system.run to execute exactly: python3 scripts/email_triage_router.py --from-inbox orion_gatewaybot@agentmail.to --limit 20 --apply. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "assistant-inbox-notify" \
  --description "Advance safe inbox work, reconcile lanes, and notify Cory" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --wake next-heartbeat \
  --message "Use system.run to execute exactly: python3 scripts/inbox_cycle.py --repo-root . --runner-max-packets 4 --stale-hours 24 --notify-max-per-run 8. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "orion-error-review" \
  --description "Review recurring ORION errors and apply safe remediations" \
  --cron "15 2 * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --wake next-heartbeat \
  --message "Use system.run to execute exactly: python3 scripts/orion_error_db.py --repo-root . review --window-hours 24 --apply-safe-fixes --escalate-incidents --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "orion-session-maintenance" \
  --description "Prune stale ORION session metadata when drift exceeds threshold" \
  --cron "45 2 * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --wake next-heartbeat \
  --message "Use system.run to execute exactly: AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "orion-ops-bundle" \
  --description "Capture a read-only ORION incident bundle with gateway, flow, and Codex posture evidence" \
  --cron "30 3 * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --wake next-heartbeat \
  --message "Use system.run to execute exactly: python3 scripts/orion_incident_bundle.py --repo-root . --write-latest --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
```

Discord variant (set a default target first):

```bash
export DISCORD_DEFAULT_POST_TARGET="user:<CORY_DISCORD_USER_ID>"
openclaw cron add \
  --name "inbox-result-notify-discord" \
  --description "Notify Cory on Discord when Notify: discord inbox packets get Result blocks" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/notify_inbox_results.py --require-notify-discord. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
```

## Dry-Run / Testing

This prints what it would send and does not require Telegram/Discord credentials:

```bash
NOTIFY_DRY_RUN=1 python3 scripts/notify_inbox_results.py --require-notify-telegram
```

You can also suppress sends while still writing notifier state:

```bash
ORION_SUPPRESS_TELEGRAM=1 python3 scripts/notify_inbox_results.py --require-notify-telegram
```

```bash
ORION_SUPPRESS_DISCORD=1 DISCORD_DEFAULT_POST_TARGET="user:<CORY_DISCORD_USER_ID>" \
  python3 scripts/notify_inbox_results.py --require-notify-discord
```
