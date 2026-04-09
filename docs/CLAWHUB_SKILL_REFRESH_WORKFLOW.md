# ClawHub Skill Refresh Workflow

Status: live workflow

## Purpose

Standardize monthly skill review around the current OpenClaw `skills` CLI surface instead of the older `openclaw clawhub ...` command shape.

## Default Review Path

Generate a durable review artifact:

```bash
python3 scripts/clawhub_skill_refresh.py \
  --output-json tmp/clawhub_skill_refresh_latest.json \
  --output-md tmp/clawhub_skill_refresh_latest.md
```

Make alias:

```bash
make assistant-skill-refresh
```

The report:
- reads tracked ClawHub-installed skills from `.clawhub/lock.json`
- runs current `openclaw skills search ...` queries
- collects `openclaw skills info <slug> --json` for tracked skills
- writes a review artifact before any update step

## Update Step

Only after review:

```bash
bash scripts/assistant_skill_refresh.sh --apply
```

Current update command:

```bash
openclaw skills update --all
```

## Stop Gates

- Do not bulk-update blindly after a search pass.
- Do not install new skills into the default posture without owner/policy review.
- Do not treat setup-gated skills as available just because they appear in search results.
