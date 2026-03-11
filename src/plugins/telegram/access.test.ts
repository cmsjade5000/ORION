import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requireOperatorAccess } from "./access";

describe("requireOperatorAccess", () => {
  const env = { ...process.env };

  beforeEach(() => {
    process.env = { ...env };
    delete process.env.ORION_TELEGRAM_ALLOWED_USER_IDS;
    delete process.env.ORION_TELEGRAM_ADMIN_IDS;
    delete process.env.ORION_TELEGRAM_CHAT_ID;
    delete process.env.ORION_CORE_TELEGRAM_TARGET;
    delete process.env.ORION_TELEGRAM_ALLOW_UNRESTRICTED_PRIVATE;
  });

  afterEach(() => {
    process.env = { ...env };
  });

  it("allows configured operator IDs", async () => {
    process.env.ORION_TELEGRAM_ALLOWED_USER_IDS = "42";
    const reply = vi.fn();
    const ok = await requireOperatorAccess(
      { from: { id: 42 }, chat: { id: 42, type: "private" }, reply },
      "Kalshi command"
    );
    expect(ok).toBe(true);
    expect(reply).not.toHaveBeenCalled();
  });

  it("rejects when ID is not allowlisted", async () => {
    process.env.ORION_TELEGRAM_ALLOWED_USER_IDS = "42";
    const reply = vi.fn(async () => {});
    const ok = await requireOperatorAccess(
      { from: { id: 7 }, chat: { id: 7, type: "private" }, reply },
      "Kalshi command"
    );
    expect(ok).toBe(false);
    expect(reply).toHaveBeenCalledTimes(1);
  });

  it("can allow private chats in explicit unrestricted mode", async () => {
    process.env.ORION_TELEGRAM_ALLOW_UNRESTRICTED_PRIVATE = "1";
    const reply = vi.fn(async () => {});
    const ok = await requireOperatorAccess(
      { from: { id: 7 }, chat: { id: 7, type: "private" }, reply },
      "Pogo command"
    );
    expect(ok).toBe(true);
    expect(reply).not.toHaveBeenCalled();
  });
});
