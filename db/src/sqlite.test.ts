import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("directive action leasing", () => {
  const originalEnv = { ...process.env };
  let dbFile = "";

  beforeEach(() => {
    vi.resetModules();
    dbFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "orion-db-")), "orion-ops.sqlite");
    process.env.ORION_DB_PATH = dbFile;
    process.env.ORION_TELEGRAM_TARGET = "123456";
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("claims actions atomically and requires matching lease data to complete", async () => {
    const db = await import("./index");

    const event = db.appendEvent({
      type: "RUN_DIAGNOSTICS",
      payload: { objective: "Check provider readiness" }
    });
    const queued = db.queueDirectiveAction(event, "123456");
    expect(queued.status).toBe("queued");

    const claimed = db.claimDirectiveAction("worker-1", 30_000);
    expect(claimed?.status).toBe("claimed");
    expect(claimed?.relayWorkerId).toBe("worker-1");
    expect(claimed?.claimToken).toBeTruthy();
    expect(claimed?.leaseUntil).toBeTruthy();

    const rejected = db.completeDirectiveAction(claimed!.id, "worker-2", claimed!.claimToken!, {
      ok: true,
      code: 200,
      responseText: "done"
    });
    expect(rejected).toBeNull();

    const completed = db.completeDirectiveAction(claimed!.id, "worker-1", claimed!.claimToken!, {
      ok: true,
      code: 200,
      responseText: "done"
    });
    expect(completed?.status).toBe("completed");
    expect(completed?.claimToken).toBeNull();
    expect(completed?.leaseUntil).toBeNull();
  });
});
