# Alert Format (Standard)

This is the standard alert/message format used by ORION and AEGIS so messages are readable, consistent, and low-noise.

## Principles

- Short, plain English.
- Newlines are real newlines (never literal `\n` sequences).
- No tool logs, stack traces, or raw config dumps.
- Include a concrete "Next" step when user action is needed.
- Include an incident id when the event is operational/security-relevant.

## Template (Preferred)

Title line:
- `AEGIS (Security Watch): <headline>`
- `AEGIS (System Watch): <headline>`
- `ORION: <headline>`

Body (keep to 3 blocks max):
- `What I saw:` one sentence (facts only)
- `What I did:` one sentence (only if an action occurred)
- `Next:` one sentence (only if action is required)

Optional:
- `Incident:` `INC-...`

## Examples

Example (security signal):

```
AEGIS (Security Watch): Many failed SSH logins

What I saw: 26 failed logins in ~5 minutes (top: 165.232.95.192, 178.62.247.172).
Next: No action taken automatically. If unexpected, review auth.log + fail2ban.
Incident: INC-AEGIS-SEC-20260208T195700Z
```

Example (availability action):

```
AEGIS (System Watch): ORION gateway restarted

What I saw: ORION health check failed.
What I did: Restarted ORION gateway once; health is OK now.
Next: No action needed.
Incident: INC-AEGIS-OPS-20260208T132500Z
```

