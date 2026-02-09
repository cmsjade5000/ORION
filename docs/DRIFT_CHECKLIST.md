# Docs Drift Checklist

Use this after any change that touches `src/`, `scripts/`, `apps/`, `openclaw.yaml`, or `openclaw.json.example`.

## 1. Start With Diffs

- Review `git status` and `git diff` first.
- If a change alters external behavior (Telegram replies, routing, scripts), assume a doc update is required.

## 2. Environment Variables

- Search for new env vars:
  - TypeScript/Node: `process.env.`
  - Shell: `${VAR}` / `$VAR`
- Then update the right docs:
  - Secrets: `KEEP.md`
  - Exposure/privilege: `SECURITY.md`
  - Setup/how-to: `docs/WORKFLOW.md`, `README.md`

## 3. Telegram Contract

If you changed Telegram commands, output rules, or user-facing behavior:
- Update `docs/TELEGRAM_STYLE_GUIDE.md`
- Update `docs/TELEGRAM_AGENT_CHAT_RULES.md`
- Update ORION’s role layer: `src/agents/ORION.md`

## 4. Delegation & Agent Roster

If you changed what ORION delegates, added a specialist, or changed ownership:
- Update `agents/INDEX.md`
- Update `docs/TASK_PACKET.md`
- Update `docs/ORION_SINGLE_BOT_ORCHESTRATION.md`

## 5. Regenerate SOUL Artifacts

- Run `make soul`.
- Expect diffs in `agents/*/SOUL.md` only when source layers changed.
