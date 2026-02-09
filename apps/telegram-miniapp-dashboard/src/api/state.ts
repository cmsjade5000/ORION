export type AgentStatus = "idle" | "busy" | "active" | "offline";

// High-level “what this agent is doing right now” for UI badges.
export type AgentActivity =
  | "idle"
  | "thinking"   // planning, reasoning, synthesizing
  | "search"     // web research / browsing
  | "files"      // reading/writing/patching repo
  | "tooling"    // running commands, automation, tooling
  | "messaging"  // telegram/email/etc
  | "error";

export type AgentState = {
  id: string;
  status: AgentStatus;
  activity?: AgentActivity;
  // Optional fixed/per-agent badge emoji (overrides `activity` badge).
  // Used for AEGIS (system state), etc.
  badge?: string | null;
};

export type OrionState = {
  status: AgentStatus;
  // High-level orchestration indicators (emojis) shown on the central ORION node.
  // Examples: routing 🧭, tooling 🛠️, synthesis ✨, thinking 🧠
  processes?: string[];
  // A small floating badge (like the sub-agents) for "what ORION is doing" (non-face icons).
  // Examples: 🔎, 📁, 🛠️, ✉️, ✅, ⚠️
  badge?: string | null;
  // Optional IO phase for the central status line.
  io?: "receiving" | "dispatching" | null;
};

export type LinkDir = "out" | "in";
export type ActiveLink = {
  agentId: string;
  dir: LinkDir;
};

export type ArtifactKind = "file";

export type Artifact = {
  id: string;
  kind: ArtifactKind;
  name: string;
  mime: string;
  url: string;
  createdAt: number;
  sizeBytes?: number | null;
  agentId?: string | null;
};

export type FeedItemKind = "response" | "event" | "artifact";

export type FeedItem = {
  id: string;
  kind: FeedItemKind;
  ts: number;
  icon?: string | null;
  text: string;
  agentId?: string | null;
};

export type WorkflowStepStatus = "pending" | "active" | "done" | "failed";

export type WorkflowStep = {
  agentId: string;
  status: WorkflowStepStatus;
};

export type WorkflowStatus = "idle" | "running" | "completed" | "failed";

export type WorkflowState = {
  id: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
  currentIndex: number;
  updatedAt: number;
};

export type LiveState = {
  ts: number;
  activeAgentId: string | null;
  // Optional richer link metadata for connection animations (directionality).
  link?: ActiveLink | null;
  agents: AgentState[];
  orion?: OrionState;
  // Optional: recent artifacts created by ORION (PDFs, exports, etc.).
  artifacts?: Artifact[];
  // Optional: short response/activity feed entries.
  feed?: FeedItem[];
  // Optional: current command workflow (multi-hop routing).
  workflow?: WorkflowState | null;
};

/**
 * API integration layer (placeholder).
 *
 * Later: ORION can expose a real endpoint that maps runtime events (agent activity,
 * task packets, sessions) into this shape.
 */
export async function fetchLiveState(opts: { initData: string }): Promise<LiveState> {
  const res = await fetch("/api/state", {
    headers: {
      // Pass initData so the server can verify the signature and bind requests to a Telegram user.
      "x-telegram-init-data": opts.initData,
    },
  });

  const data = (await res.json().catch(() => null)) as any;
  if (!res.ok) {
    const msg =
      data && data.error && typeof data.error.message === "string"
        ? `${data.error.code || "ERROR"}: ${data.error.message}`
        : `HTTP ${res.status}`;
    throw new Error(`state fetch failed: ${msg}`);
  }

  return data as LiveState;
}
