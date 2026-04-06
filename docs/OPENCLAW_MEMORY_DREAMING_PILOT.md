# OpenClaw Memory Dreaming Pilot

This repo tracks the OpenClaw `2026.4.5` dreaming surface as a conservative pilot for ORION.

## Goal

Adopt memory consolidation without turning background promotion into a silent source of false long-term memory.

## Current ORION Stance

- Keep `memory-lancedb` as the active template default.
- Do not move dreaming onto the assistant critical path yet.
- Keep `MEMORY.md` as curated durable memory.
- Treat `DREAMS.md` as operator-review output, not a truth source.

## Official OpenClaw Surface

Verified against the `2026.4.5` release notes and CLI/docs:
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

## Recommended ORION Pilot

1. Fix memory backend reliability first.
2. Switch the active memory slot only when ready:
   - from `memory-lancedb`
   - to `memory-core`
3. Enable dreaming with the default nightly cadence first.
4. Review `openclaw memory rem-harness --json` output before trusting automatic promotion.
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

Use this before changing the active memory slot or enabling `/dreaming`.

Dreaming also depends on ORION memory recall seeing canonical daily notes. If
`agents.list[].memorySearch.sources` is left on `["sessions"]`, OpenClaw will
not record the `source: "memory"` hits that feed short-term recall.

## Template Shape

Minimal pilot config:

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
- Do not let background promotion replace deliberate review of `MEMORY.md`.
- Do not leave ORION on `memorySearch.sources = ["sessions"]` if you expect dreaming recall to populate.
- Do not rely on undocumented internal dreaming thresholds in repo templates; keep the template on the public config surface only.
