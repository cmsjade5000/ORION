# Email Triage Router

Owner: ORION

Purpose:
- Inspect recent inbound AgentMail messages.
- Run threat preflight (sender, link domains only, attachment types only).
- Create `TASK_PACKET v1` delegations in `tasks/INBOX/<AGENT>.md`.

Policy alignment:
- `docs/EMAIL_POLICY.md` (ORION-only inbox, quarantine on suspicious/high-risk).
- `docs/TASK_PACKET.md` (packet structure + notify behavior).

## Script

- Path: `scripts/email_triage_router.py`
- Default mode: dry-run (no file writes)
- Apply mode: `--apply` (append packets + update state)

## Usage

Dry-run against live inbox:

```bash
python3 scripts/email_triage_router.py \
  --from-inbox orion_gatewaybot@agentmail.to \
  --limit 20
```

Apply writes:

```bash
python3 scripts/email_triage_router.py \
  --from-inbox orion_gatewaybot@agentmail.to \
  --limit 20 \
  --apply
```

Offline fixture run (for testing):

```bash
python3 scripts/email_triage_router.py \
  --messages-json tmp/agentmail_messages_fixture.json
```

Optional trust list:

```bash
EMAIL_TRIAGE_TRUSTED_DOMAINS="icloud.com,agentmail.to,openai.com" \
python3 scripts/email_triage_router.py --limit 20
```

## Routing Rules (summary)

- `POLARIS`: default admin requests and all quarantined/high-risk emails.
- `ATLAS`: ops/setup/infra execution requests.
- `LEDGER`: spending/value tradeoff requests.
- `SCRIBE`: writing/drafting requests.
- `WIRE`: sources-first news/update retrieval requests.
- `EMBER`: emotional-support/crisis language.

## State

State file:
- `tmp/email_triage_state.json`

Tracks:
- `processed_message_ids`
- `written_keys` (idempotency keys)
- `updated_at`

## Cron (compatibility only)

If you explicitly need the older `agentTurn` wrapper path, run every 5 minutes in an isolated ORION session:

```bash
openclaw cron add \
  --name "email-triage-router" \
  --description "Route inbound email into specialist inbox Task Packets" \
  --cron "*/5 * * * *" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --message "Run python3 scripts/email_triage_router.py --limit 20 --apply. Respond NO_REPLY."
```

The default local path is the direct maintenance bundle (`scripts/install_orion_local_maintenance_launchagents.sh`), which runs `assistant-email-triage` without paying for an extra model turn.

## Safety

- Do not click links from inbound email in this workflow.
- Do not open/execute attachments in this workflow.
- Quarantine indicators force review-first handling.
- Outbound actions stay confirmation-gated via ORION.
