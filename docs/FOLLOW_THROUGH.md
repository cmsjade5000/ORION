# Follow-Through (Stop Needing "Continue")

Problem: ORION can delegate multi-step work to specialists, but results may land asynchronously (for example in `tasks/INBOX/*.md`). If nothing triggers a user-facing follow-up, Cory ends up prodding ORION with “continue” messages.

Goal: when a delegated packet completes, Cory gets a short Telegram or Discord update automatically.

For the admin-copilot posture, this is required infrastructure rather than optional polish.

## Mechanism (Single-Bot Mode)

1. ORION creates a Task Packet in `tasks/INBOX/<AGENT>.md` and includes:
   - `Notify: telegram` or `Notify: discord` (or `Notify: telegram,discord`)
2. The specialist writes a `Result:` block under that packet when done.
3. A periodic run executes:
   - `python3 scripts/notify_inbox_results.py --require-notify-telegram` (Telegram)
   - `python3 scripts/notify_inbox_results.py --require-notify-discord` (Discord)
   - Optional policy gate hardening:
     - `--policy-rules config/orion_policy_rules.json`
     - `--policy-mode audit|block` (default `audit`)
4. The notifier sends a concise update and remembers what it already notified (state in `tmp/inbox_notify_state.json`).

Notes:
- The notifier is bounded and non-spammy (default max 3 results per run).
- Heartbeat outputs remain `NO_REPLY`; the script does the send.
  - Telegram: direct API call (token file or env var).
  - Discord: uses `openclaw message send --channel discord ...` (so this script never touches the Discord token).

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

## Cron (Recommended)

Add the assistant follow-through crons after Telegram inbound is verified:

```bash
./scripts/install_orion_assistant_crons.sh
```

Equivalent manual commands:

```bash
openclaw cron add \
  --name "inbox-result-notify" \
  --description "Notify Cory when Notify: telegram inbox packets get Result blocks" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/notify_inbox_results.py --require-notify-telegram. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "task-loop-heartbeat" \
  --description "Reconcile packet/ticket lifecycle and fail loud on stale pending packets" \
  --cron "*/5 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/task_execution_loop.py --apply --strict-stale --stale-hours 24. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

openclaw cron add \
  --name "task-loop-weekly-reconcile" \
  --description "Weekly reconcile sweep for inbox/results/tickets notes" \
  --cron "15 9 * * 1" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/task_execution_loop.py --apply --stale-hours 72. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
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

You can also suppress sends (while still writing notifier state and emitting Mini App events):

```bash
ORION_SUPPRESS_TELEGRAM=1 python3 scripts/notify_inbox_results.py --require-notify-telegram
```

```bash
ORION_SUPPRESS_DISCORD=1 DISCORD_DEFAULT_POST_TARGET="user:<CORY_DISCORD_USER_ID>" \
  python3 scripts/notify_inbox_results.py --require-notify-discord
```
