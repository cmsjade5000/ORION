import { describe, expect, it } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const { extractApprovalFromText, findJobById, isCompletedJob, packetPreview } = require("./state.cjs");

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
});

describe("mini app delegated job preview", () => {
  function withSummary(summary: object, run: (root: string) => void) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "orion-miniapp-state-"));
    try {
      const jobsDir = path.join(root, "tasks", "JOBS");
      fs.mkdirSync(jobsDir, { recursive: true });
      fs.writeFileSync(path.join(jobsDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
      run(root);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  }

  it("treats complete and ok-result jobs as completed", () => {
    expect(isCompletedJob({ state: "complete", result: { status: "pending" } })).toBe(true);
    expect(isCompletedJob({ state: "pending_verification", result: { status: "ok" } })).toBe(true);
    expect(isCompletedJob({ state: "blocked", result: { status: "failed" } })).toBe(false);
    expect(isCompletedJob({ state: "queued", result: { status: "pending" } })).toBe(false);
  });

  it("omits completed jobs from active previews while preserving direct lookup", () => {
    withSummary(
      {
        counts: { complete: 1, pending_verification: 1, queued: 1, blocked: 1 },
        jobs: [
          { job_id: "done-state", state: "complete", result: { status: "pending" } },
          { job_id: "done-result", state: "pending_verification", result: { status: "ok" } },
          { job_id: "queued", state: "queued", result: { status: "pending" } },
          { job_id: "blocked", state: "blocked", result: { status: "failed" } },
        ],
      },
      (root) => {
        const preview = packetPreview(root);
        expect(preview.jobs.map((job: { job_id: string }) => job.job_id)).toEqual(["queued", "blocked"]);
        expect(findJobById(root, "done-result")).toMatchObject({ job_id: "done-result" });
      }
    );
  });
});
