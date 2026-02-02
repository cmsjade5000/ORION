# Security

## Threat Model
What I am protecting against.
What I explicitly am not protecting against.
Assumptions about risk.

## Trust Zones
macOS host
Gateway VM
Agents
External services

## Access Rules
SSH access policy.
Who can log in.
How access is granted and revoked.

## Network Assumptions
What outbound access is allowed.
What inbound access is forbidden.
What is never exposed.

## Agent Safety Rules
What agents are never allowed to do.
Actions that always require human approval.
Actions agents may only recommend, not execute.

## Secrets & The Keep
High-level rules.
Pointer to KEEP.md.
What never touches an agent context.

## Incident Response
What to do if something feels wrong.
How to pause or shut things down safely.
