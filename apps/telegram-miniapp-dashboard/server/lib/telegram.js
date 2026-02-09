import crypto from "node:crypto";

export function parseTelegramInitData(initData) {
  const params = new URLSearchParams(String(initData || ""));
  const out = {};
  for (const [k, v] of params.entries()) out[k] = v;
  return out;
}

/**
 * Verifies Telegram Mini App initData per:
 * https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
 *
 * Returns `{ ok: true, params }` on success, or `{ ok: false, error, params }` on failure.
 */
export function verifyTelegramInitData({
  initData,
  botToken,
  maxAgeSec,
  clockSkewSec = 60,
  nowMs = Date.now(),
}) {
  const params = parseTelegramInitData(initData);

  const hashRaw = typeof params.hash === "string" ? params.hash : "";
  const hash = hashRaw.trim().toLowerCase();
  if (!hash) return { ok: false, error: "missing_hash", params };

  const pairs = [];
  for (const [k, v] of Object.entries(params)) {
    if (k === "hash") continue;
    pairs.push([k, String(v)]);
  }
  pairs.sort((a, b) => a[0].localeCompare(b[0]));
  const dataCheckString = pairs.map(([k, v]) => `${k}=${v}`).join("\n");

  const secretKey = crypto
    .createHmac("sha256", "WebAppData")
    .update(String(botToken || ""))
    .digest();
  const computed = crypto
    .createHmac("sha256", secretKey)
    .update(dataCheckString)
    .digest("hex");

  const safeEq =
    computed.length === hash.length &&
    crypto.timingSafeEqual(Buffer.from(computed, "utf8"), Buffer.from(hash, "utf8"));
  if (!safeEq) return { ok: false, error: "bad_sig", params };

  const authDate = Number.parseInt(String(params.auth_date || ""), 10);
  if (!Number.isFinite(authDate) || authDate <= 0) {
    return { ok: false, error: "bad_auth_date", params };
  }

  const nowSec = Math.floor(nowMs / 1000);
  const ageSec = nowSec - authDate;

  // Reject initData "from the future" beyond expected clock skew.
  if (Number.isFinite(clockSkewSec) && clockSkewSec >= 0 && ageSec < -clockSkewSec) {
    return { ok: false, error: "future_auth_date", params };
  }

  if (Number.isFinite(maxAgeSec) && maxAgeSec > 0 && ageSec > maxAgeSec) {
    return { ok: false, error: "expired", params };
  }

  return { ok: true, params };
}

