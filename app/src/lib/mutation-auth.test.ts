import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authorizeMutationRequest } from "./mutation-auth";

function buildTelegramInitData(botToken: string, params: Record<string, string>): string {
  const entries = Object.entries(params).sort(([left], [right]) => left.localeCompare(right));
  const dataCheckString = entries.map(([key, value]) => `${key}=${value}`).join("\n");
  const secret = createHmac("sha256", "WebAppData").update(botToken).digest();
  const hash = createHmac("sha256", secret).update(dataCheckString).digest("hex");
  const query = new URLSearchParams(params);
  query.set("hash", hash);
  return query.toString();
}

describe("authorizeMutationRequest", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
    delete process.env.TELEGRAM_BOT_TOKEN;
    delete process.env.TELEGRAM_BOT_TOKEN_FILE;
    delete process.env.TELEGRAM_TOKEN_FILE;
    delete process.env.MINIAPP_INGEST_TOKEN;
    delete process.env.INGEST_TOKEN;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("returns 401 when credentials are missing", () => {
    process.env.ORION_API_BEARER_TOKEN = "secret";
    const request = new Request("https://example.test/api/events", { method: "POST" });
    const result = authorizeMutationRequest(request);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(401);
      expect(result.code).toBe("UNAUTHORIZED");
    }
  });

  it("accepts a valid bearer token", () => {
    process.env.ORION_API_BEARER_TOKEN = "secret";
    const request = new Request("https://example.test/api/events", {
      method: "POST",
      headers: { authorization: "Bearer secret" },
    });
    const result = authorizeMutationRequest(request);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.mode).toBe("bearer");
    }
  });

  it("rejects expired telegram initData", () => {
    process.env.TELEGRAM_BOT_TOKEN = "bot-token";
    process.env.TELEGRAM_INITDATA_MAX_AGE_SEC = "60";
    const authDate = String(Math.floor(Date.now() / 1000) - 3_600);
    const initData = buildTelegramInitData("bot-token", {
      auth_date: authDate,
      user: JSON.stringify({ id: 123456 }),
    });
    const request = new Request("https://example.test/api/events", {
      method: "POST",
      headers: { "x-telegram-init-data": initData },
    });
    const result = authorizeMutationRequest(request);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.status).toBe(403);
      expect(result.error).toContain("expired");
    }
  });
});
