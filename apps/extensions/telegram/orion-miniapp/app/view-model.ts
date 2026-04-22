import type { InboxPayload, JobItem, MiniAppScreen } from "./types";

export function screenFromStartapp(startapp?: string): MiniAppScreen {
  const value = String(startapp || "").trim().toLowerCase();
  if (["approvals", "approval", "work", "inbox"].includes(value)) return "inbox";
  if (["today", "review"].includes(value)) return "today";
  return "chat";
}

export function screenTitle(screen: MiniAppScreen): string {
  if (screen === "inbox") return "Mission Inbox";
  if (screen === "today") return "Today";
  return "Bridge Chat";
}

export function formatRelativeTime(ageMs: number): string {
  const minutes = Math.max(1, Math.round(ageMs / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function statusTone(status?: string): "good" | "warn" | "alert" | "neutral" {
  const value = String(status || "").toLowerCase();
  if (value.includes("complete") || value.includes("succeeded")) return "good";
  if (value.includes("blocked") || value.includes("failed")) return "alert";
  if (value.includes("pending")) return "warn";
  return "neutral";
}

export function isFollowupActionable(job: JobItem): boolean {
  const state = String(job.state || "").toLowerCase();
  return state === "blocked" || state === "pending_verification";
}

export function buildInboxSections(inbox: InboxPayload) {
  return [
    {
      key: "approvals",
      title: "Approvals",
      description: "Direct action back into Telegram when live context exists.",
      count: inbox.approvals.length,
    },
    {
      key: "blocked",
      title: "Blocked Work",
      description: "Items that need a nudge, context, or a follow-up packet.",
      count: inbox.blockedJobs.length,
    },
    {
      key: "pending",
      title: "Pending Verification",
      description: "Work that finished a pass but still needs confirmation.",
      count: inbox.pendingVerificationJobs.length,
    },
  ];
}
