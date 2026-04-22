# OpenClaw Memory Dreaming

This repo tracks the OpenClaw `2026.4.21` dreaming surface as the active dreaming path for ORION's `memory-core` runtime.

## Goal

Adopt memory consolidation without turning background promotion into a silent source of false long-term memory.

## Current ORION Stance

- Keep `memory-lancedb` as the active template default.
- Use dreaming as the active background consolidation path when runtime is on `memory-core`.
- Keep `MEMORY.md` as the compact durable memory file for intentionally maintained notes.
- Treat `DREAMS.md` as operator-review output generated from dreaming.

## Official OpenClaw Surface

Verified against the `2026.4.21` CLI/docs:
- Config path: `plugins.entries.memory-core.config.dreaming`
- Public config keys:
  - `enabled`
  - `frequency`
- Chat command:
  - `/dreaming status`
  - `/dreaming on`
  - `/dreaming off`
  - `/dreaming help`
- CLI review:
  - `openclaw memory status --deep`
  - `openclaw memory promote`
  - `openclaw memory promote --apply`
  - `openclaw memory promote-explain "<selector>"`
  - `openclaw memory rem-harness --json`

Default managed sweep cadence:
- `0 3 * * *`

Upstream notes in `2026.4.20` and `2026.4.21` that matter for ORION core:
- dreaming remains on the public `memory-core` surface
- dreaming narrative cleanup was hardened so fallback cleanup reuses hashed narrative session keys instead of leaking sub-sessions
- session pruning is more aggressive by default, which matters when ORION accumulates long-lived cron and executor histories
- Active Memory exists upstream as an optional plugin, but ORION core keeps the checked-in template conservative
- bundled Codex provider support and `commands.list` are runtime capabilities, not a reason to widen ORION core ownership

## Recommended ORION Path

1. Fix memory backend reliability first.
2. Switch the active memory slot only when ready:
   - from `memory-lancedb`
   - to `memory-core`
3. Enable dreaming with the default nightly cadence first.
4. Review `openclaw memory rem-harness --json` output when diagnosing low promotion yield.
5. Use `openclaw memory promote-explain` on any questionable candidate before allowing deep promotion to shape `MEMORY.md`.

## Repo Preview Path

This repo now provides a non-destructive preview command:

```bash
make dreaming-preview
```

It runs:
- `openclaw memory status --deep --json`
- `openclaw memory rem-harness --json`
- `openclaw memory promote --limit 10`

Artifacts:
- `tmp/openclaw_memory_dreaming_preview_latest.json`
- `tmp/openclaw_memory_dreaming_preview_latest.md`

Use this before changing the active memory slot, debugging promotion yield, or enabling `/dreaming`.

The preview now also surfaces:
- recall-store timestamp and entry count
- deep candidate count
- threshold blocker keys (`score`, `recallCount`, `uniqueQueries`) for top candidates
- whether canonical daily memory is newer than the current recall store

For deterministic direct ORION turns in this workspace, prefer the guarded wrapper path over raw `openclaw agent`:

```bash
make dreaming-status
make dreaming-help
make dreaming-on
make dreaming-off
```

Those targets route through `scripts/openclaw_guarded_turn.py`, which intercepts `/dreaming ...` and runs `scripts/assistant_status.py` directly instead of relying on model-side slash-command interpretation.

Dreaming also depends on ORION memory recall seeing canonical daily notes. If
`agents.list[].memorySearch.sources` is left on `["sessions"]`, OpenClaw will
not record the `source: "memory"` hits that feed short-term recall.

Nightly ORION maintenance is expected to run in this order:
1. session maintenance
2. slugged-memory consolidation into canonical daily files
3. `openclaw memory index --agent main --force`
4. the managed dreaming promotion sweep

If the `Memory Reindex` section in `tasks/NOTES/session-maintenance.md` is
missing or failed, treat dreaming freshness as pending verification.

## Template Shape

Minimal config:

```json
{
  "plugins": {
    "slots": {
      "memory": "memory-core"
    },
    "entries": {
      "memory-core": {
        "enabled": true,
        "config": {
          "dreaming": {
            "enabled": true,
            "frequency": "0 3 * * *"
          }
        }
      }
    }
  }
}
```

## What To Avoid

- Do not enable dreaming while embeddings/search are failing.
- Do not treat `DREAMS.md` as a fact store.
- Do not let background promotion replace deliberate maintenance of `MEMORY.md` when a compact durable note is needed.
- Do not leave ORION on `memorySearch.sources = ["sessions"]` if you expect dreaming recall to populate.
- Do not rely on undocumented internal dreaming thresholds in repo templates; keep the template on the public config surface only.
