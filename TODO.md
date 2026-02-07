# TODO

This is the short, current work queue for getting ORION live locally.

## Go-Live (Local)

- [ ] Install gateway service: `openclaw gateway install`
- [ ] Start gateway service: `openclaw gateway start`
- [ ] Run health/repair: `openclaw doctor --repair`
- [ ] Run security audit: `openclaw security audit --deep`
- [ ] Probe channels: `openclaw channels status --probe`
- [ ] Verify ORION-only Telegram behavior (no specialist delivers to Telegram)
- [ ] Verify specialist delegation:
  - ORION -> `atlas` via Task Packet
  - ORION -> `node` via Task Packet
- [ ] Create minimal cron jobs using Task Packets (deliver=false by default)

## Cleanup / Hardening

- [ ] Rotate any secrets that were pasted into chat during setup.
- [ ] Add `gitleaks` to your local toolchain and run `skills/secrets-scan` before pushes.

## AEGIS (Future, Remote)

- [ ] Decide where AEGIS will run (Hetzner / other) and what it should monitor (gateway process vs health endpoint).
