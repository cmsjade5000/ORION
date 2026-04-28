import { describe, expect, it } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const { extractApprovalFromText, persistQueueRequest, readQueueRequests, updateQueueRequestStatus } = require("./state.cjs");

describe("mini app approval scanning", () => {
  it("extracts approve commands", () => {
    expect(extractApprovalFromText("Please run `/approve abc123 allow-once`")).toEqual({
      approvalId: "abc123",
      suggestedDecision: "allow-once",
    });
  });

  it("extracts deny commands", () => {
    expect(extractApprovalFromText("If you do not want to proceed, use `/deny ff12aa90`.")).toEqual({
      approvalId: "ff12aa90",
      suggestedDecision: "deny",
    });
  });

  it("persists and updates mini app queue requests", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "orion-miniapp-queue-"));
    try {
      const request = persistQueueRequest(root, {
        jobId: "job-1",
        status: "queued",
        message: "Captured for POLARIS.",
        intakePath: "tasks/INTAKE/example.md",
        packetNumber: 5,
        createdAt: "2026-04-28T13:00:00.000Z",
      });

      expect(readQueueRequests(root)).toEqual([request]);
      expect(updateQueueRequestStatus(root, request.id, "refresh_delayed")).toMatchObject({
        id: request.id,
        status: "refresh_delayed",
      });
      expect(readQueueRequests(root)[0]).toMatchObject({ id: request.id, status: "refresh_delayed" });
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
