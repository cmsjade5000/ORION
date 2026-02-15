import { Bot } from "grammy";
import { registerKalshiCommands } from "./index";

describe("Kalshi command registration", () => {
  it("registers /kalshi_status and /kalshi_digest", () => {
    const bot = { command: jest.fn() } as any as Bot;
    registerKalshiCommands(bot);
    expect(bot.command).toHaveBeenCalledWith("kalshi_status", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("kalshi_digest", expect.any(Function));
  });
});

