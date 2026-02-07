# Identity (Generated)

This repo treats agent identity as a generated artifact.

## Source Of Truth

- User preferences: `USER.md`
- Shared identity/policy layers: `src/core/shared/`
- Per-agent role layers: `src/agents/`

## Generated Outputs

- ORION identity: `agents/ORION/SOUL.md` (also linked as `SOUL.md`)
- Specialist identities: `agents/<AGENT>/SOUL.md`

Do not hand-edit `agents/*/SOUL.md`. Make changes in the source-of-truth files and re-run the Soul Factory.

## Soul Factory

Generate all SOULs:

```bash
./scripts/soul_factory.sh --all
```
