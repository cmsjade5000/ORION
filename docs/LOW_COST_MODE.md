# Low-Cost Mode

This repository now treats **low-cost mode as the permanent default posture**.

The goal is simple: ORION is a side project, so the default path should minimize paid model usage without making the repo unusable.

## Default Rules

- Prefer local files, existing repo docs, and deterministic scripts before any hosted model call.
- Prefer local-only or read-only verification before live probes or smoke turns.
- Keep prompts narrow and context scoped to the files or contracts being changed.
- Avoid speculative fan-out, broad research passes, and premium search/tooling unless they materially change the result.
- Treat premium OpenAI/Codex lanes as explicit opt-in, not as ambient defaults.

## Runtime Defaults

- Checked-in OpenClaw templates default ORION to `openrouter/openrouter/free`.
- Default fallbacks stay in the cheap/free lane first.
- Provider-native Codex web search stays disabled by default.
- Kimi and premium OpenAI/Codex lanes remain available only as intentional escalation paths.

## Planning And Code Modifications

For ORION repo planning or implementation work:

- plan from local repo context first
- prefer targeted edits over broad rewrites
- prefer targeted tests over full live benchmark suites
- do not run automatic `openclaw models status --probe`
- do not run automatic `openclaw agent` smoke turns against paid providers
- do not use premium model lanes unless the user explicitly asks or a bounded low-cost attempt already failed

## Validation Defaults

- `make operator-health-bundle` remains read-only/local unless `ALLOW_LIVE_MODEL_PROBE=1` or `ALLOW_LIVE_SMOKE=1` is set deliberately.
- Provider benchmark scripts are for intentional readiness/eval work, not normal implementation verification.
- Repo-side config and contract tests should be sufficient for ordinary ORION code changes.

## Escalation Rule

Escalate out of low-cost mode only when at least one of these is true:

- Cory explicitly opts into premium spend
- a bounded low-cost attempt failed and the blocker is concrete
- the task is high-stakes enough that cheaper lanes are not defensible

If escalation happens, say so plainly and keep the scope bounded.
