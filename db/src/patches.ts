import type { PatchDefinition, PatchId } from "./types";

export const PATCHES: PatchDefinition[] = [
  {
    id: "focus-firmware-v1-2",
    name: "Focus Firmware v1.2",
    description: "Improves clarity gain during sync and diagnostic cycles."
  },
  {
    id: "stability-patch",
    name: "Stability Patch",
    description: "Buffers stability dips and reinforces recovery operations."
  },
  {
    id: "alignment-module",
    name: "Alignment Module",
    description: "Strengthens mission alignment from structured progress."
  },
  {
    id: "curiosity-scanner",
    name: "Curiosity Scanner",
    description: "Amplifies exploratory directives and note processing."
  },
  {
    id: "cache-optimizer",
    name: "Cache Optimizer",
    description: "Makes cache flushes more restorative for the core."
  },
  {
    id: "throughput-multiplier",
    name: "Throughput Multiplier",
    description: "Trades extra startup load for stronger completion gains."
  }
];

export function isPatchId(value: string): value is PatchId {
  return PATCHES.some((patch) => patch.id === value);
}
