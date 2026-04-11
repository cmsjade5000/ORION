import { describe, expect, it, vi } from "vitest";
import { Bot } from "grammy";
import {
  __test_only_applyStepInput,
  __test_only_buildDeepLink,
  registerFlicChatRouter,
} from "../index";

describe("Flic chat router registration", () => {
  it("registers commands and text handler", () => {
    const bot = {
      command: vi.fn(),
      on: vi.fn(),
    };

    registerFlicChatRouter(bot as any as Bot);

    expect(bot.command).toHaveBeenCalledWith("flic", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("flicreset", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("reroll", expect.any(Function));
    expect(bot.on).toHaveBeenCalledWith("message:text", expect.any(Function));
  });

  it("fails closed outside production when deep link base URL is unset", async () => {
    const env = { ...process.env };
    delete process.env.FLIC_VAULT_BASE_URL;
    process.env.NODE_ENV = "test";
    await expect(__test_only_buildDeepLink({ q: "neo noir" })).rejects.toThrow(
      /FLIC_VAULT_BASE_URL is required outside production/
    );
    process.env = env;
  });

  it("parses mood/genre/runtime into normalized params", () => {
    const flow: any = { step: "mood_genre", params: {}, turn: 0 };
    let params = __test_only_applyStepInput(flow, "heartfelt comedy please");
    expect(params.moods).toBe("Heartfelt");
    expect(params.genres).toBe("Comedy");

    flow.step = "runtime";
    params = __test_only_applyStepInput(flow, "about 1.5 hours");
    expect(params.runtime_max).toBe(90);
  });

  it("passes through non-flic private DMs to downstream middleware", async () => {
    const bot = {
      command: vi.fn(),
      on: vi.fn(),
    };

    registerFlicChatRouter(bot as any as Bot);

    const onCall = bot.on.mock.calls.find((call) => call[0] === "message:text");
    expect(onCall).toBeTruthy();
    const handler = onCall?.[1] as (ctx: any, next: () => Promise<void>) => Promise<void>;

    const ctx = {
      chat: { type: "private", id: 42 },
      message: { text: "hello there" },
      reply: vi.fn(),
    };
    const next = vi.fn(async () => {});

    await handler(ctx, next);

    expect(next).toHaveBeenCalledTimes(1);
    expect(ctx.reply).not.toHaveBeenCalled();
  });
});
