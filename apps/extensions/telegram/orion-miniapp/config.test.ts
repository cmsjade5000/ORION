import { afterEach, describe, expect, it, vi } from "vitest";

const fs = require("node:fs");
const os = require("node:os");

const originalHome = os.homedir;

afterEach(() => {
  vi.restoreAllMocks();
  os.homedir = originalHome;
});

describe("mini app config", () => {
  it("hydrates operator ids from openclaw telegram allowFrom config", () => {
    const fakeHome = "/tmp/orion-miniapp-config-test";
    os.homedir = () => fakeHome;
    const realReadFileSync = fs.readFileSync.bind(fs) as typeof fs.readFileSync;
    vi.spyOn(fs, "readFileSync").mockImplementation(((...rawArgs: any[]) => {
      const [target, ...args] = rawArgs;
      if (String(target) === `${fakeHome}/.openclaw/openclaw.json`) {
        return JSON.stringify({
          channels: {
            telegram: {
              allowFrom: [8471523294],
            },
          },
        });
      }
      return realReadFileSync(target, ...args);
    }) as typeof fs.readFileSync);

    const { configuredOperatorIds } = require("./config.cjs");
    expect(configuredOperatorIds()).toContain("8471523294");
  });
});
