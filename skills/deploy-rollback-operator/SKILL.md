---
name: deploy-rollback-operator
description: STRATUS rollback decision and verification checklist. No destructive defaults; includes stop gates.
metadata:
  invocation: user
---

# Deploy Rollback Operator (STRATUS)

Use when a deploy/release looks suspect and you need a consistent rollback decision path.

## Inputs To Capture (Task Packet)

- What changed (commit/PR, release id)
- Blast radius (service/env/users impacted)
- Current health signals (error rate, latency, health checks)
- Last known good version
- Rollback mechanism available (tag, release, image, config revert)

## Decision Gates

Rollback is favored when:
- user-facing errors are elevated and trending worse
- health checks are failing or flapping
- a known-good version exists and rollback is reversible

Do NOT rollback blindly when:
- data migrations are one-way
- rollback would break compatibility (schema/API mismatch)

## Stop Gates (Ask Cory / ORION Before Proceeding)

- Any destructive data change or irreversible migration.
- Any credential/secret rotation.
- Any broad infra change (firewall, routing, DNS).

## Rollback Procedure (Generic)

1. Freeze: stop additional deploys; capture current version identifiers.
2. Verify: confirm failures correlate with the release window.
3. Roll back: switch to last known good (mechanism-specific).
4. Validate: run health checks and confirm key user flows are restored.
5. Document: append a short incident note + prevention follow-up Task Packet.

## Post-Rollback Verification Checklist

- service health endpoint OK
- error rate back to baseline
- latency within normal range
- logs show no continued crash loops
- if applicable: background jobs stable and not retry-storming

