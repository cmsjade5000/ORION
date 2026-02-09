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
};

export type OrionState = {
  status: AgentStatus;
  // High-level orchestration indicators (emojis) shown on the central ORION node.
  // Examples: routing 🧭, tooling 🛠️, synthesis ✨, thinking 🧠
  processes?: string[];
};

export type LinkDir = "out" | "in";
export type ActiveLink = {
  agentId: string;
  dir: LinkDir;
};

export type LiveState = {
  ts: number;
  activeAgentId: string | null;
  // Optional richer link metadata for connection animations (directionality).
  link?: ActiveLink | null;
  agents: AgentState[];
  orion?: OrionState;
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

  if (!res.ok) {
    throw new Error(`state fetch failed: ${res.status}`);
  }

  return (await res.json()) as LiveState;
}
