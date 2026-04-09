# Working Memory

Last verified: 2026-03-12

## Current Goal

Refocus ORION into a bounded-proactive admin copilot:

- Telegram remains the primary user-facing channel.
- POLARIS is the default route for reminders, calendar prep, notes capture, follow-through, and daily review.

## Current Status

- OpenClaw workspace points at this repo.
- Isolated specialist agents are configured locally.
- Assistant command scaffolding is repo-backed: `/today`, `/capture`, `/followups`, `/review`.

## Known Blockers / Risks

- Telegram inbound (DM -> ORION auto-reply) must be verified before enabling assistant crons.
- Hook/plugin settings still live in the runtime config under `~/.openclaw/openclaw.json`; repo files only provide the template.
- Ensure no secrets ever land in Git (run `skills/secrets-scan` before pushes).

## Next Steps

1. Verify Telegram inbound DM works:
   - DM `@Orion_GatewayBot` and confirm ORION responds.
2. Refresh the assistant agenda:
   - `python3 scripts/assistant_status.py --cmd refresh --json`
3. Verify assistant command flow:
   - `/today`
   - `/capture test item`
   - `/followups`
   - `/review`
4. Enable assistant crons after Telegram verification:
   - `./scripts/install_orion_assistant_crons.sh`
