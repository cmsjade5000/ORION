---
name: pr-manager
description: "Detect, review, and (optionally) merge GitHub PRs for this repo using gh CLI with explicit user authorization."
---

# PR Manager Skill

## Scope

This skill helps ORION handle PRs created from any environment (including iPhone/Codex cloud) by operating against GitHub.

## Rules

- Never merge without explicit Cory authorization.
- Prefer per-PR opt-in via label: `orion-automerge`.
- For every merge, append an `INCIDENT v1` entry to `tasks/INCIDENTS.md`.

## Detect PRs

List open PRs:

```bash
gh pr list --repo cmsjade5000/ORION --state open
```

Optional poll helper (creates Task Packets under `tasks/PR/`):

```bash
REPO=cmsjade5000/ORION ./scripts/pr_poll.sh
```

## Review

Checkout PR and review locally:

```bash
gh pr checkout <pr-number> --repo cmsjade5000/ORION
git diff --stat origin/main...HEAD
gh pr checks <pr-number> --repo cmsjade5000/ORION
```

## Merge (Only If Authorized)

Authorized when:
- Cory explicitly says “merge PR <n>”, or
- the PR has label `orion-automerge`.

Merge:

```bash
gh pr merge <pr-number> --repo cmsjade5000/ORION --squash --delete-branch
```

