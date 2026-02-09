import crypto from "node:crypto";

function b64urlEncode(buf) {
  return Buffer.from(buf).toString("base64url");
}

function b64urlDecodeUtf8(s) {
  return Buffer.from(String(s), "base64url").toString("utf8");
}

/**
 * Signed short-lived token (HMAC) for EventSource auth.
 * This is a privacy measure so we don't put Telegram initData in URLs.
 */
export function issueSseToken({
  initDataSha256,
  secret,
  ttlMs = 10 * 60_000,
  nowMs = Date.now(),
}) {
  const payload = {
    v: 1,
    iat: nowMs,
    exp: nowMs + Math.max(5_000, Number(ttlMs) || 0),
    initDataSha256: String(initDataSha256 || ""),
  };
  const payloadB64 = b64urlEncode(JSON.stringify(payload));
  const sig = crypto.createHmac("sha256", String(secret || "")).update(payloadB64).digest();
  const sigB64 = b64urlEncode(sig);
  return { token: `${payloadB64}.${sigB64}`, expiresAt: payload.exp };
}

export function verifySseToken({ token, secret, nowMs = Date.now() }) {
  const parts = String(token || "").split(".");
  if (parts.length !== 2) return { ok: false, error: "bad_format" };
  const [payloadB64, sigB64] = parts;
  const sig = Buffer.from(sigB64, "base64url");
  const expected = crypto.createHmac("sha256", String(secret || "")).update(payloadB64).digest();
  if (sig.length !== expected.length || !crypto.timingSafeEqual(sig, expected)) {
    return { ok: false, error: "bad_sig" };
  }

  let payload;
  try {
    payload = JSON.parse(b64urlDecodeUtf8(payloadB64));
  } catch {
    return { ok: false, error: "bad_payload" };
  }

  if (!payload || payload.v !== 1) return { ok: false, error: "bad_claims" };
  if (typeof payload.exp !== "number" || payload.exp <= nowMs) return { ok: false, error: "expired" };
  if (typeof payload.iat !== "number" || payload.iat > nowMs + 60_000) return { ok: false, error: "bad_iat" };
  if (typeof payload.initDataSha256 !== "string" || payload.initDataSha256.length < 16) {
    return { ok: false, error: "bad_claims" };
  }

  return { ok: true, payload };
}

