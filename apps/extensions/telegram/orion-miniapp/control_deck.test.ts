import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

const {
  approveAction,
  getOrCreateLoopbackToken,
  listCleanupCandidates,
  previewAction,
  restoreQuarantineItem,
  validateLocalToken,
} = require("./control_deck.cjs");

function tempWorkspace() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "orion-control-deck-"));
}

function writeCandidate(root: string, name = "scratch-cache.txt") {
  const candidateDir = path.join(root, "tmp", "control-deck-candidates");
  fs.mkdirSync(candidateDir, { recursive: true });
  const candidatePath = path.join(candidateDir, name);
  fs.writeFileSync(candidatePath, "temporary generated data", "utf8");
  return candidatePath;
}

describe("control deck backend", () => {
  it("preview cleanup reports candidates without mutating them", async () => {
    const root = tempWorkspace();
    try {
      const candidatePath = writeCandidate(root);
      const [candidate] = listCleanupCandidates(root);

      const preview = await previewAction(root, "preview-cleanup", { candidateIds: [candidate.id] });

      expect(preview).toMatchObject({
        actionId: "preview-cleanup",
        mutation: false,
        requiresApproval: false,
      });
      expect(preview.candidates).toHaveLength(1);
      expect(fs.existsSync(candidatePath)).toBe(true);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("quarantine requires explicit confirmation", async () => {
    const root = tempWorkspace();
    try {
      const candidatePath = writeCandidate(root);
      const [candidate] = listCleanupCandidates(root);

      const result = await approveAction(root, "quarantine-cleanup", { candidateId: candidate.id });

      expect(result).toMatchObject({
        status: "blocked",
        message: "confirmation-required",
        mutation: false,
      });
      expect(fs.existsSync(candidatePath)).toBe(true);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("quarantines and restores a cleanup candidate by item id", async () => {
    const root = tempWorkspace();
    try {
      const candidatePath = writeCandidate(root);
      const [candidate] = listCleanupCandidates(root);

      const quarantined = await approveAction(root, "quarantine-cleanup", {
        candidateId: candidate.id,
        confirm: "QUARANTINE",
      });

      expect(quarantined.status).toBe("succeeded");
      expect(quarantined.restoreToken).toMatch(/^quarantine_/);
      expect(fs.existsSync(candidatePath)).toBe(false);

      const restored = restoreQuarantineItem(root, quarantined.restoreToken, { confirm: "RESTORE" });

      expect(restored).toMatchObject({
        ok: true,
        status: "succeeded",
        mutation: true,
      });
      expect(fs.existsSync(candidatePath)).toBe(true);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it("accepts local loopback tokens only from loopback requests", () => {
    const root = tempWorkspace();
    try {
      const token = getOrCreateLoopbackToken(root);
      const loopbackReq = {
        url: "/api/control-deck/snapshot",
        headers: { authorization: `Bearer ${token}`, host: "127.0.0.1:8787" },
        socket: { remoteAddress: "127.0.0.1" },
      };
      const remoteReq = {
        ...loopbackReq,
        socket: { remoteAddress: "10.0.0.22" },
      };

      expect(validateLocalToken(loopbackReq, root)).toBe(true);
      expect(validateLocalToken(remoteReq, root)).toBe(false);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
