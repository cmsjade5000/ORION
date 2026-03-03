# Cron Hygiene Changes (March 2026)

Date applied: 2026-03-02
Owner: ATLAS (implemented by ORION runtime ops)

## Changes Applied

- Disabled 5 non-essential high-frequency QUEST arc-field-guide cron jobs:
  - `30800b89-18d6-4270-af1a-73ccea0e1383`
  - `dd1d3968-df7d-4f9c-8593-9a03ec85bebe`
  - `658f4f75-52cb-4145-b388-054eae5dde05`
  - `32998ac9-3874-4b5b-a87f-c700784cae62`
  - `c5873e09-107a-4e19-b7da-e73987659a0a`
- Reduced poll frequency for inbox notify:
  - `0f7ece50-e808-463f-b3c6-6a6764097109` from `*/2 * * * *` to `*/5 * * * *`.
- Reduced LEDGER sports paper polling load:
  - `3adbdf11-8d7e-4eb2-8552-80cbf5384812` from `0 * * * * *` to `0 */5 * * * *`.
- Archived stale WhatsApp recovery payloads from delivery queue to:
  - `/Users/corystoner/.openclaw/delivery-queue-archive/20260302-205027`

## Before / After

- Enabled cron jobs: `19 -> 14`
- Enabled job channel mismatches: `0 -> 0`
- Delivery queue files (stale failures): `16 -> 0`

## Verification Commands

```bash
python3 - <<'PY'
import json, pathlib
cfg=json.loads(pathlib.Path('/Users/corystoner/.openclaw/openclaw.json').read_text())
enabled_channels={k for k,v in (cfg.get('channels') or {}).items() if isinstance(v,dict) and v.get('enabled') is True}
enabled_plugins={k for k,v in (cfg.get('plugins',{}).get('entries') or {}).items() if isinstance(v,dict) and v.get('enabled') is True}
j=json.loads(pathlib.Path('/Users/corystoner/.openclaw/cron/jobs.json').read_text())
bad=[]
for job in j.get('jobs',[]):
    if not job.get('enabled'): continue
    ch=((job.get('delivery') or {}).get('channel') or 'none')
    if ch in ('none','last'): continue
    if ch not in enabled_channels or ch not in enabled_plugins:
        bad.append((job.get('id'), ch))
print('enabled_jobs',sum(1 for x in j.get('jobs',[]) if x.get('enabled')))
print('mismatches',bad)
PY
```

## Notes

- This step focuses on load/noise reduction and channel correctness.
- Functional workflow intent for disabled QUEST arc jobs should be re-approved before re-enable.
