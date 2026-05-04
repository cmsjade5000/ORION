import { describe, expect, it, vi } from "vitest";
import { Bot } from "grammy";
import { registerDashboard } from "../index";

describe("Agent Dashboard command registration", () => {
  it("should register the /agents command", async () => {
    const ctxCommand = { chat: { id: 123, type: "private" }, from: { id: 123 }, reply: vi.fn() };
    const bot = {
      command: vi.fn(),
      callbackQuery: vi.fn(),
    };

    registerDashboard(bot as any as Bot);

    expect(bot.command).toHaveBeenCalledWith(
      "agents",
      expect.any(Function)
    );
    expect(bot.callbackQuery).toHaveBeenCalledWith(
      /^agent_([A-Z]+)$/,
      expect.any(Function)
    );

    const commandHandler = bot.command.mock.calls[0]?.[1];
    const callbackHandler = bot.callbackQuery.mock.calls[0]?.[1];
    expect(commandHandler).toBeDefined();
    expect(callbackHandler).toBeDefined();

    const deniedCtx = {
      chat: { id: 456, type: "private" },
      from: { id: 456 },
      reply: vi.fn(),
      answerCallbackQuery: vi.fn(),
    };
    await expect(commandHandler(deniedCtx as never)).resolves.toBeUndefined();
    const deniedMessage = deniedCtx.reply.mock.calls[0]?.[0];
    expect(String(deniedMessage)).toContain("Agents dashboard");
    await expect(callbackHandler(deniedCtx as never)).resolves.toBeUndefined();
    expect(deniedCtx.reply).toHaveBeenCalledTimes(2);
    expect(deniedCtx.answerCallbackQuery).toHaveBeenCalledTimes(1);

    process.env.ORION_TELEGRAM_ALLOWED_USER_IDS = "123";
    return commandHandler(ctxCommand);
  });
});
