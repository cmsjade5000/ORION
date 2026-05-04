import { describe, expect, it, vi } from "vitest";
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
      expect(updateQueueRequestStatus(root, request.id, "completed")).toMatchObject({
        id: request.id,
        status: "completed",
      });
      expect(readQueueRequests(root)[0]).toMatchObject({ id: request.id, status: "completed" });
      expect(updateQueueRequestStatus(root, request.id, "acknowledged")).toMatchObject({
        id: request.id,
        status: "acknowledged",
      });
      expect(readQueueRequests(root)[0]).toMatchObject({ id: request.id, status: "acknowledged" });
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
        nextStep: "Approve it once, deny it, or ask POLARIS to rework the packet if the request itself is wrong.",
        taskPacketApproval: {
          eligible: true,
          decisions: ["approve-once", "deny"],
        },
        packetText: expect.stringContaining("Objective: Recover the queue."),
        resultLines: ["Status: BLOCKED", "Need Cory context."],
      });
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("surfaces recorded task packet approval decisions and queued owner followups", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "orion-miniapp-decision-"));
    try {
      fs.mkdirSync(path.join(root, "tasks", "APPROVALS"), { recursive: true });
      fs.mkdirSync(path.join(root, "tasks", "JOBS"), { recursive: true });
      fs.mkdirSync(path.join(root, "tasks", "INBOX"), { recursive: true });
      fs.writeFileSync(
        path.join(root, "tasks", "APPROVALS", "task-packet-approvals.jsonl"),
        JSON.stringify({
          id: "tpa-1",
          job_id: "job-1",
          workflow_id: "wf-1",
          decision: "approve_once",
          created_at: "2026-04-30T16:51:57Z",
          actor: "telegram:1 Cory",
          queued_packet: "tasks/INBOX/ATLAS.md",
        }) + "\n",
        "utf8"
      );
      fs.writeFileSync(
        path.join(root, "tasks", "JOBS", "summary.json"),
        JSON.stringify({
          counts: { blocked: 1, queued: 1 },
          jobs: [
            {
              job_id: "job-1",
              workflow_id: "wf-1",
              state: "blocked",
              owner: "ATLAS",
              objective: "Recover the queue.",
              inbox: { path: "tasks/INBOX/ATLAS.md", line: 3 },
            },
            {
              job_id: "job-2",
              workflow_id: "wf-1",
              state: "queued",
              owner: "ATLAS",
              objective: "Continue the approved Task Packet exactly once: Recover the queue.",
              inbox: { path: "tasks/INBOX/ATLAS.md", line: 20 },
            },
          ],
        }),
        "utf8"
      );
      fs.writeFileSync(
        path.join(root, "tasks", "INBOX", "ATLAS.md"),
        ["# ATLAS", "", "TASK_PACKET v1", "Owner: ATLAS", "Objective: Recover the queue."].join("\n"),
        "utf8"
      );

      expect(jobDetail(root, "job-1")).toMatchObject({
        needSummary: "Approved once. A scoped owner follow-up packet has been queued.",
        nextStep: "Watch the queued owner follow-up: job-2.",
        taskPacketApproval: {
          eligible: false,
          latestDecision: {
            id: "tpa-1",
            decision: "approve_once",
          },
          followupJob: {
            job_id: "job-2",
            state: "queued",
          },
        },
      });
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("returns null for malformed json payloads from assistant subprocesses", async () => {
    const { runJsonCommand } = require("./state.cjs");

    await expect(
      runJsonCommand("node", ["-e", "process.stdout.write('not json')"], path.join(os.tmpdir(), "orion-miniapp"))
    ).resolves.toBeNull();
  });
});
