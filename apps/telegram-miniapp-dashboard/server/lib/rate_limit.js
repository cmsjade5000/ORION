/**
 * Simple fixed-window in-memory rate limiter.
 *
 * Notes:
 * - Best-effort only (per-instance). For multi-instance production, also enforce at the edge.
 * - Designed to be dependency-free.
 */
export function createFixedWindowLimiter({ windowMs, max, name = "rl", nowMs = () => Date.now() }) {
  const W = Math.max(250, Number(windowMs) || 0);
  const M = Math.max(1, Number(max) || 1);

  /** @type {Map<string, { count: number, resetAt: number }>} */
  const buckets = new Map();

  // Light cleanup to prevent unbounded growth.
  let lastCleanup = 0;
  const cleanup = (now) => {
    if (now - lastCleanup < 10_000) return;
    lastCleanup = now;
    for (const [k, v] of buckets.entries()) {
      if (v.resetAt <= now) buckets.delete(k);
    }
  };

  const keyFor = (key) => `${name}:${String(key || "")}`;

  const hit = (key) => {
    const now = nowMs();
    cleanup(now);

    const k = keyFor(key);
    const cur = buckets.get(k);
    if (!cur || cur.resetAt <= now) {
      const resetAt = now + W;
      buckets.set(k, { count: 1, resetAt });
      return { ok: true, limit: M, remaining: Math.max(0, M - 1), resetAt };
    }

    cur.count += 1;
    const ok = cur.count <= M;
    return { ok, limit: M, remaining: Math.max(0, M - cur.count), resetAt: cur.resetAt };
  };

  return { hit };
}

