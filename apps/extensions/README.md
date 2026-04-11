# Extension Surfaces

This tree holds product-specific or non-core ORION surfaces that are intentionally outside the default ORION core control plane.

Current layout:
- `telegram/`
  - non-core Telegram command surfaces such as Flic, Kalshi, and Pogo
- `kalshi/docs/`
  - Kalshi-specific product docs and operator runbooks
- `pogo/docs/`
  - Pogo-specific product docs

Rules:
- Do not import extension Telegram handlers into `src/plugins/telegram/index.ts`.
- Keep ORION core docs and installers pointed at core-owned surfaces only.
- If an extension needs a separate runtime posture, put that setup next to the extension instead of widening ORION core.
