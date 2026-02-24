# Personal Ops Automations

Use `scripts/install_orion_personal_ops_crons.sh` to manage two lightweight weekday jobs.

## Purpose

- Morning job: start-of-day planning/triage and next-action setup.
- Evening job: end-of-day reset, capture outcomes, and prep tomorrow.

## Defaults

- Timezone: `America/New_York` (ET).
- Morning schedule: weekdays at `07:15` (`15 7 * * 1-5`).
- Evening schedule: weekdays at `20:30` (`30 20 * * 1-5`).

## Install

Dry-run (preview only, no cron changes):

```bash
scripts/install_orion_personal_ops_crons.sh
```

Apply (create/update cron jobs):

```bash
scripts/install_orion_personal_ops_crons.sh --apply
```

## Customize Schedule Or Timezone

Use installer flags to override defaults:

```bash
scripts/install_orion_personal_ops_crons.sh \
  --apply \
  --morning-cron "15 7 * * 1-5" \
  --evening-cron "30 20 * * 1-5" \
  --tz "America/New_York"
```

Check available options:

```bash
scripts/install_orion_personal_ops_crons.sh --help
```

## Verify Jobs

```bash
openclaw cron list --all
```

Optional filter:

```bash
openclaw cron list --all | rg -i "personal|morning|evening"
```

## Run Jobs Immediately (Testing)

1. Find each job id from `openclaw cron list --all`.
2. Run each job once:

```bash
openclaw cron run <morning_job_id>
openclaw cron run <evening_job_id>
```

## Decision-Assistant Note (On-Demand Only)

Keep decision-assistant unscheduled. Trigger it only when needed:

```bash
Ask ORION: "Use decision-assistant. Decision: <decision>. Options: <option_a>|<option_b>. Constraints: <constraints>. Return recommendation, assumptions, and next step."
```

## Safety

- Do not invent facts.
- Label assumptions explicitly.
- Require explicit confirmation before irreversible actions.
