import { describe, expect, it, vi } from "vitest";
import { Bot } from "grammy";
import { registerMiniApp } from "./index";

describe("Mini App command registration", () => {
  it("registers /miniapp and /core aliases", () => {
    const bot = { command: vi.fn() } as any as Bot;
    registerMiniApp(bot);

    expect(bot.command).toHaveBeenCalledWith("miniapp", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("core", expect.any(Function));
  });
});
