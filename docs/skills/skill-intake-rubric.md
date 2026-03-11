# Skill Intake Rubric

Last updated: 2026-03-02
Scope: Candidate skills considered for ORION runtime integration.
Policy: Staged canary is mandatory for any skill accepted by this rubric.

## Scoring Model

Score each dimension from 0 to 5.
Weighted points are computed as: `(dimension_score / 5) * weight`.
Total possible score is 100.

| Dimension | Weight | What "5" Looks Like | What "0" Looks Like |
| --- | ---: | --- | --- |
| Trustworthiness | 20 | Verified maintainer identity, clear provenance, clean security posture, transparent changelog | Unknown author/source, unverifiable artifacts, integrity concerns |
| Maintenance | 15 | Active maintenance, recent updates, issue/PR responsiveness, clear versioning | Abandoned or stale, no release process, unresolved critical issues |
| Capability Fit | 20 | Directly addresses a validated ORION need with measurable benefit | Marginal overlap or no concrete fit to known use cases |
| Risk | 15 | Low blast radius, explicit boundaries, minimal permissions, reversible behavior | High privilege, uncontrolled side effects, undefined failure modes |
| Observability | 15 | Emits usable logs/metrics/events for success and failure states | Opaque behavior, no reliable telemetry or debugging hooks |
| Rollback | 15 | Clear and tested disable/remove path with no data corruption risk | No safe rollback path or rollback requires destructive recovery |

## Pass / Reject Rules

Pass threshold:
- `Total score >= 78`, and
- No single dimension below `3`, and
- All hard reject criteria below are false.

Soft hold (do not canary yet):
- `Total score` between `70` and `77`, or
- One dimension at `2` with explicit mitigation owner/date.

Reject criteria (automatic reject):
- Fails source validation rules in this document.
- Requires secrets exfiltration, unsafe privilege escalation, or unbounded network execution.
- Missing license terms or license incompatible with project usage.
- No documented rollback path.
- Known unresolved critical security issue without compensating controls.

## Evidence Requirements

Record evidence for each scored dimension:
- Source URL(s).
- Version or commit SHA evaluated.
- Date checked.
- Reviewer initials.
- Reproduction notes and local command transcript path.

Minimum artifact locations:
- Intake notes: `docs/skills/shortlist-2026-03-weekly.md`
- Canary protocol reference: `docs/skills/canary-protocol.md`
- Results logging: `docs/skills/canary-results-2026-03.md`

## Source Validation Rules (Online-Discovered Skills)

A candidate discovered online is valid only if all checks pass:

1. Origin authenticity
- Repository or package source is canonical (official org/user, not an unverified mirror).
- Download location is HTTPS and checksum/signature can be recorded when available.

2. Maintainer verification
- Maintainer identity is attributable across at least two independent signals (for example org website + signed release or maintainer profile + long-lived activity history).

3. Integrity and supply-chain checks
- Pin exact version/commit.
- Capture dependency manifest and check for suspicious post-install hooks or dynamic remote code loading.

4. Security posture
- Review issue tracker and advisories for open critical vulnerabilities.
- Confirm no required behavior conflicts with `SECURITY.md` and `KEEP.md`.

5. License and usage rights
- License is present, clear, and compatible with repo policies.

6. Reproducibility
- Installation and basic behavior are reproducible in a controlled local environment.
- Command transcript and observed outputs are linked in evidence notes.

7. Documentation sufficiency
- Setup, operational constraints, and rollback are documented enough to run staged canary without guesswork.

If any check cannot be proven with evidence, mark status `pending verification` and treat as reject until resolved.
