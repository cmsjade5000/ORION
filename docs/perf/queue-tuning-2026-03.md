# Queue Tuning Results (March 2026)

Date applied: 2026-03-02 (America/New_York)  
Track: B (lane-wait reduction tuning + logs)

## Lane-Wait Analysis (last 24h before tuning)

Source: `~/.openclaw/logs/gateway.err.log`

- Total lane-wait events: `20`
- P95 wait: `34,527 ms`
- Max wait: `35,296 ms`
- Primary contention window: `2026-03-03T00:58:34Z` to `2026-03-03T00:58:52Z` (`16/20` events, queueAhead peak `14`)
- Secondary window: `2026-03-03T01:25:29Z` to `2026-03-03T01:25:38Z` (`2` events)
- Concurrent error storm in the primary window: repeated `Delivery failed (whatsapp ... Unknown channel: whatsapp)` lines.

## Exact Changes Applied

### Cron tuning (`~/.openclaw/cron/jobs.json`)

- `inbox-result-notify` (`0f7ece50-e808-463f-b3c6-6a6764097109`)
  - `expr`: `*/5 * * * *` -> `2-59/10 * * * *`
  - Rationale: non-critical notify job moved off top-of-5-minute boundaries and reduced to every 10 minutes.
- `polymarket-sports-paper-60s` (`3adbdf11-8d7e-4eb2-8552-80cbf5384812`)
  - `expr`: `0 */5 * * * *` -> `20 */5 * * * *`
  - `staggerMs`: `0` -> `20000`
  - Rationale: keep trading workflow active while offsetting simultaneous starts.
- `kalshi-ref-arb-5m` (`bd523bc9-ba21-4c44-99ca-97c84e85f827`)
  - No schedule change (kept active and unchanged).

Backups:
- `~/.openclaw/cron/jobs.json.bak.trackb.1772506711781`

### Runtime concurrency (`~/.openclaw/openclaw.json`)

- `agents.defaults.maxConcurrent`: `6` -> `7`
- `agents.defaults.subagents.maxConcurrent`: `10` -> `11`

Backups:
- `~/.openclaw/openclaw.json.bak.trackb.1772506711781`

## Restart + Verification Commands

```bash
openclaw gateway restart
openclaw gateway status
openclaw gateway health
openclaw cron list
python3 scripts/collect_reliability_snapshot.py --hours 24
```

Observed restart output:

- `Restarted LaunchAgent: gui/501/ai.openclaw.gateway`
- `Runtime: running (pid 77805, state active)`
- `RPC probe: ok`
- `Gateway Health: OK`

## Before/After Quick Stats

Baseline before tuning (snapshot: `eval/history/reliability-20260303-025458.json`):

- `lane_wait_count`: `20`
- `lane_wait_p95_ms`: `34527`
- `cron_enabled`: `17`

Immediate post-change snapshot (`eval/history/reliability-20260303-025854.json`):

- `lane_wait_count`: `20`
- `lane_wait_p95_ms`: `34527`
- `cron_enabled`: `19`
- `delivery_queue_files`: `0`
- `eval_gate`: `pass`

Note: no immediate lane-wait metric drop is expected yet because the 24h window still contains the pre-change spike interval.

## Remaining Risks / Blockers (SLO-R1/R2)

- The dominant spike window aligns with a WhatsApp delivery error storm, so cron staggering alone may not clear SLO-R1/R2.
- `polymarket-sports-paper-60s` naming/schedule semantics remain inconsistent (name implies 60s cadence, stored cron is 5-minute style with second offset); scheduler behavior should be re-validated after full 24h soak.
- Need a full post-change 24h window before claiming SLO-R1/R2 pass/fail.

## WhatsApp Suppression Follow-Up (Task B)

Date applied: 2026-03-02 22:05 EST

- Hardened enabled cron jobs with delivery fallback to `last+announce` so they cannot route to stale WhatsApp session context:
  - `a02afa86-bac2-41ff-bc26-5f08651a905f` (`kalshi-digest-reliability-daily`): `last+announce` -> `last+none`
  - `67c29ebf-49e9-4dbe-bd9a-84fe7e7ef1f6` (`kalshi-digest-delivery-guard`): `last+announce` -> `last+none`
- Cleared stale specialist runtime session route context that still pointed to WhatsApp in:
  - `~/.openclaw/agents/{atlas,ember,ledger,node,pixel,pulse,quest,scribe,stratus,wire}/sessions/sessions.json`
  - For each `agent:<id>:main`, removed `channel/lastChannel/deliveryContext` when set to `whatsapp`.
- Archived remaining WhatsApp failed-delivery payload to stop recovery retry noise:
  - moved `~/.openclaw/delivery-queue/failed/993a44e9-14de-4a6f-b759-53cd04c9b7a3.json`
  - to `~/.openclaw/delivery-queue-archive/taskb-whatsapp-20260302-220532/`

Verification commands:

```bash
python3 scripts/collect_reliability_snapshot.py --hours 24
jq -r '[.jobs[] | select(.enabled==true and ((.delivery.channel // "" | ascii_downcase)=="whatsapp"))] | length' ~/.openclaw/cron/jobs.json
jq -r '[.jobs[] | select(.enabled==true and ((.delivery.channel // "" | ascii_downcase)=="last") and ((.delivery.mode // "" | ascii_downcase)=="announce"))] | length' ~/.openclaw/cron/jobs.json
tail -n 200 ~/.openclaw/logs/gateway.err.log | rg -n "whatsapp|Unknown channel|Outbound not configured" -S
```

Immediate results:

- Reliability snapshot: `delivery_queue_files: 0`, `eval_gate: pass`.
- Enabled cron delivery to `whatsapp`: `0`.
- Enabled cron delivery using `last+announce`: `0`.
- Best-effort log tail after change window: no newer WhatsApp unknown-channel lines observed; latest matching lines remain pre-change window (`2026-03-02 20:17:54 -05:00` and `2026-03-03 01:03:38Z`).
