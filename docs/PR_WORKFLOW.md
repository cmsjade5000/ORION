# PR Workflow (Cory iPhone -> GitHub -> ORION Review -> Merge)

Goal: if Cory opens a PR against `cmsjade5000/ORION`, ORION can reliably:
1. Detect it.
2. Pull/checkout the PR branch locally.
3. Review + run checks.
4. Merge to `main` when explicitly authorized.

## Non-Negotiables

- No irreversible actions without explicit user authorization.
- ORION should not auto-merge a PR unless Cory has opted-in per-PR.

## Detection

ORION uses the GitHub CLI (`gh`) to list PRs:

```bash
gh pr list --repo cmsjade5000/ORION --state open
```

Optional polling helper:
- `scripts/pr_poll.sh`

## Review

Local checkout and review:

```bash
gh pr checkout <pr-number>
git status
git diff --stat origin/main...HEAD
```

Recommended checks:
- `gh pr checks <pr-number> --repo cmsjade5000/ORION`
- `make soul` if any identity source-of-truth changed
- project-specific tests (if present)

## Merge Policy (Explicit Opt-In)

ORION only merges when **one** of the following is true:
- Cory comments "merge" to ORION in Slack/Telegram for that PR, or
- Cory adds the label `orion-automerge` to the PR (preferred for iPhone-first workflow).

Merge command (squash default):

```bash
gh pr merge <pr-number> --repo cmsjade5000/ORION --squash --delete-branch
```

## Audit

When a PR is merged (or an emergency bypass happens), ORION appends an `INCIDENT v1` entry to:
- `tasks/INCIDENTS.md`

