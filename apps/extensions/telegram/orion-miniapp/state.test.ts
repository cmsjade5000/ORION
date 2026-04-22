import { describe, expect, it } from "vitest";

const { extractApprovalFromText } = require("./state.cjs");

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
