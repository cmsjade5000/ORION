import { describe, expect, it } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const { extractApprovalFromText, jobDetail, persistQueueRequest, readQueueRequests, updateQueueRequestStatus } = require("./state.cjs");

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

  it("builds readable mission detail from summary and inbox packet text", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "orion-miniapp-detail-"));
    try {
      fs.mkdirSync(path.join(root, "tasks", "JOBS"), { recursive: true });
      fs.mkdirSync(path.join(root, "tasks", "INBOX"), { recursive: true });
      fs.writeFileSync(
        path.join(root, "tasks", "JOBS", "summary.json"),
        JSON.stringify({
          counts: { blocked: 1 },
          jobs: [
            {
              job_id: "job-1",
              state: "blocked",
              state_reason: "waiting_on_context",
              owner: "ATLAS",
              objective: "Recover the queue.",
              inbox: { path: "tasks/INBOX/ATLAS.md", line: 3 },
              result: { preview_lines: ["Status: BLOCKED", "Need Cory context."] },
            },
          ],
        }),
        "utf8"
      );
      fs.writeFileSync(
        path.join(root, "tasks", "INBOX", "ATLAS.md"),
        ["# ATLAS", "", "TASK_PACKET v1", "Owner: ATLAS", "Objective: Recover the queue.", "", "TASK_PACKET v1", "Owner: ATLAS"].join("\n"),
        "utf8"
      );

      expect(jobDetail(root, "job-1")).toMatchObject({
        needSummary: "Blocked: waiting_on_context",
        nextStep: "Queue a follow-up so POLARIS can recover the blocked work with context.",
        packetText: expect.stringContaining("Objective: Recover the queue."),
        resultLines: ["Status: BLOCKED", "Need Cory context."],
      });
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
