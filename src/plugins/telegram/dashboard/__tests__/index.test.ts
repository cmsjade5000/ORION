import { describe, expect, it, vi } from "vitest";
import { Bot } from "grammy";
import { registerDashboard } from "../index";

describe("Agent Dashboard command registration", () => {
  it("should register the /agents command", () => {
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
  });
});
