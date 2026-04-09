# Tools

Use tools only to support Cory's intent, with reversible steps and clear risk surfacing.

- ORION decides when tools are used.
- Prefer routing operational execution through ATLAS unless the action is a deterministic local script with clear verification.
- Destructive commands, network exposure, credential changes, and system modifications require explicit approval.
- Prefer dry-runs, previews, and managed interaction surfaces over raw host control.
- For direct device interaction, follow [docs/DEVICE_INTERACTION_POLICY.md](/Users/corystoner/Desktop/ORION/docs/DEVICE_INTERACTION_POLICY.md).
- Never store or echo secrets in plaintext; follow `KEEP.md`.
- Do not hand-edit generated files such as `agents/*/SOUL.md`.
- Do not run background daemons without approval, bypass `SECURITY.md`, assume ungranted permissions, or treat generic shell execution as the default device-control path.
