const crypto = require("node:crypto");

function parseRawInitData(raw) {
  const params = new URLSearchParams(String(raw || ""));
  const fields = {};
  for (const [key, value] of params.entries()) {
    fields[key] = value;
  }
  return fields;
}

function parseInitData(raw) {
  const fields = parseRawInitData(raw);
  if (fields.user) {
    try {
      fields.user = JSON.parse(fields.user);
    } catch {
      // Keep raw string if Telegram payload is malformed.
    }
  }
  if (fields.receiver) {
    try {
      fields.receiver = JSON.parse(fields.receiver);
    } catch {
      // Keep raw string if Telegram payload is malformed.
    }
  }
  if (fields.chat) {
    try {
      fields.chat = JSON.parse(fields.chat);
    } catch {
      // Keep raw string if Telegram payload is malformed.
    }
  }
  return fields;
}

function serializeValue(value) {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function dataCheckString(fields) {
  return Object.keys(fields)
    .filter((key) => key !== "hash")
    .sort()
    .map((key) => `${key}=${serializeValue(fields[key])}`)
    .join("\n");
}

function hmacSecret(botToken) {
  return crypto.createHmac("sha256", "WebAppData").update(String(botToken || ""), "utf8").digest();
}

function signInitData(fields, botToken) {
  const payload = { ...fields };
  delete payload.hash;
  return crypto.createHmac("sha256", hmacSecret(botToken)).update(dataCheckString(payload), "utf8").digest("hex");
}

function validateInitData(raw, botToken, options = {}) {
  const rawFields = parseRawInitData(raw);
  const fields = parseInitData(raw);
  const expectedHash = String(rawFields.hash || "");
  if (!expectedHash) {
    return { ok: false, reason: "missing-hash", fields };
  }
  if (!botToken) {
    return { ok: false, reason: "missing-bot-token", fields };
  }

  const actualHash = signInitData(rawFields, botToken);
  const matches = crypto.timingSafeEqual(Buffer.from(expectedHash), Buffer.from(actualHash));
  if (!matches) {
    return { ok: false, reason: "bad-hash", fields };
  }

  const maxAgeSeconds = Math.max(1, Number.parseInt(String(options.maxAgeSeconds || "43200"), 10));
  const authDate = Number.parseInt(String(fields.auth_date || "0"), 10);
  if (!Number.isFinite(authDate) || authDate <= 0) {
    return { ok: false, reason: "missing-auth-date", fields };
  }

  const ageSeconds = Math.floor(Date.now() / 1000) - authDate;
  if (ageSeconds > maxAgeSeconds) {
    return { ok: false, reason: "expired", ageSeconds, fields };
  }

  return { ok: true, ageSeconds, fields };
}

module.exports = {
  dataCheckString,
  parseInitData,
  signInitData,
  validateInitData,
};
