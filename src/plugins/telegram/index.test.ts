import { describe, expect, it, vi } from "vitest";
import type { Bot } from "grammy";
import { setupTelegramPlugin } from "./index";

describe("setupTelegramPlugin", () => {
  it("registers only the ORION core Telegram surfaces", () => {
    const bot = {
      command: vi.fn(),
      on: vi.fn(),
      callbackQuery: vi.fn(),
    } as unknown as Bot;

    setupTelegramPlugin(bot);

    expect(bot.command).toHaveBeenCalledWith("today", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("orion", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("agents", expect.any(Function));
    expect(bot.command).not.toHaveBeenCalledWith("paper_help", expect.any(Function));
    expect(bot.command).not.toHaveBeenCalledWith("pogo_help", expect.any(Function));
    expect(bot.command).not.toHaveBeenCalledWith("flic", expect.any(Function));
  });
});
