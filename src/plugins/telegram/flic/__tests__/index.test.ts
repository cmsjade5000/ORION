import { Bot } from "grammy";
import { __test_only_applyStepInput, registerFlicChatRouter } from "../index";

describe("Flic chat router registration", () => {
  it("registers commands and text handler", () => {
    const bot = {
      command: jest.fn(),
      on: jest.fn(),
    } as any as Bot;

    registerFlicChatRouter(bot);

    expect(bot.command).toHaveBeenCalledWith("flic", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("flicreset", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("reroll", expect.any(Function));
    expect(bot.on).toHaveBeenCalledWith("message:text", expect.any(Function));
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
      command: jest.fn(),
      on: jest.fn(),
    } as any as Bot;

    registerFlicChatRouter(bot);

    const onCall = (bot.on as jest.Mock).mock.calls.find((call) => call[0] === "message:text");
    expect(onCall).toBeTruthy();
    const handler = onCall?.[1] as (ctx: any, next: () => Promise<void>) => Promise<void>;

    const ctx = {
      chat: { type: "private", id: 42 },
      message: { text: "hello there" },
      reply: jest.fn(),
    };
    const next = jest.fn(async () => {});

    await handler(ctx, next);

    expect(next).toHaveBeenCalledTimes(1);
    expect(ctx.reply).not.toHaveBeenCalled();
  });
});
