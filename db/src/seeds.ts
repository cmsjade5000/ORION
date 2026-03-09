import type { EventInput } from "./types";

function isoFromOffset(hoursAgo: number): string {
  return new Date(Date.now() - hoursAgo * 3600000).toISOString();
}

export function buildSeedEvents(): EventInput[] {
  return [
    { type: "DAILY_SYNC", payload: {}, createdAt: isoFromOffset(140) },
    {
      type: "TASK_CREATED",
      payload: { id: "seed-01", title: "Triage inbound requests", taskType: "triage" },
      createdAt: isoFromOffset(139)
    },
    { type: "TASK_STARTED", payload: { id: "seed-01" }, createdAt: isoFromOffset(138) },
    {
      type: "TASK_COMPLETED",
      payload: { id: "seed-01", outcome: "success" },
      createdAt: isoFromOffset(130)
    },
    { type: "RUN_DIAGNOSTICS", payload: {}, createdAt: isoFromOffset(96) },
    {
      type: "INJECT_TASK_PACKET",
      payload: { type: "research" },
      createdAt: isoFromOffset(78)
    },
    {
      type: "TASK_CREATED",
      payload: { id: "seed-02", title: "Refactor parser edge cases", taskType: "refactor" },
      createdAt: isoFromOffset(76)
    },
    {
      type: "PATCH_APPLIED",
      payload: { patchId: "stability-patch" },
      createdAt: isoFromOffset(52)
    },
    {
      type: "NOTE_ADDED",
      payload: { text: "Core remains stable under moderate queue pressure." },
      createdAt: isoFromOffset(20)
    },
    {
      type: "DAILY_SYNC",
      payload: {},
      createdAt: isoFromOffset(8)
    },
    {
      type: "SIMULATION_RUN",
      payload: { drillType: "risk_check", result: "pass" },
      createdAt: isoFromOffset(2)
    }
  ];
}
