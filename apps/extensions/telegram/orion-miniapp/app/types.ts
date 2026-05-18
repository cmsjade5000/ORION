export type MiniAppScreen = "deck" | "home" | "compose" | "queue" | "task" | "status" | "activity" | "settings";

export type TaskStatus = "queued" | "running" | "waiting" | "needs_input" | "done" | "failed" | "stuck";

export type QueueFilter = "active" | "pending" | "needs_input" | "done" | "failed";

export type Task = {
  id: string;
  owner: string;
  objective: string;
  state: string;
  status: TaskStatus;
  statusReason?: string | null;
  inboxPath?: string | null;
};

export type SystemStatus = {
  api: "online" | "partial" | "offline";
  queue: "healthy" | "degraded" | "offline";
  worker: "healthy" | "degraded" | "offline";
  updatedAt: string | null;
  message?: string;
};

export type ActivityItem = {
  id: string;
  type: "request" | "task" | "system" | "approval";
  title: string;
  detail: string;
  atMs: number;
};

export type QuickAction = {
  key: string;
  title: string;
  label: string;
  template?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  createdAt: number;
};

export type ChatConversation = {
  conversationId: string;
  sessionId: string;
  updatedAt: number;
  messages: ChatMessage[];
};

export type ChatRunEvent = {
  id: number;
  type: string;
  ts: number;
  message?: string;
  status?: string;
  conversation?: ChatConversation;
};

export type ChatRunPayload = {
  runId: string;
  conversationId: string;
  sessionId: string;
  status: string;
  createdAt: number;
  completedAt?: number | null;
  error?: string | null;
  lastMessage?: string | null;
  events: ChatRunEvent[];
  conversation: ChatConversation;
};

export type BootstrapPayload = {
  appName: string;
  startapp: string;
  user: { id: number; first_name?: string; username?: string } | null;
  hasQueryId: boolean;
  operatorIdsConfigured: boolean;
  conversation: ChatConversation;
};

export type ApprovalItem = {
  approvalId: string;
  suggestedDecision: "allow-once" | "allow-always" | "deny";
  summary: string;
  label: string;
  sessionId: string;
  sessionKey: string;
  ts: number;
  ageMs: number;
};

export type JobItem = {
  job_id: string;
  workflow_id?: string;
  state: string;
  state_reason?: string;
  owner: string;
  objective: string;
  notify?: string;
  result?: {
    job_state?: string;
    status?: string;
    present?: boolean;
  };
  inbox?: {
    path?: string;
    line?: number;
  };
};

export type JobDetailPayload = {
  job: JobItem;
  needSummary: string;
  nextStep: string;
  packetText: string;
  resultLines: string[];
  relatedApprovals: ApprovalItem[];
  taskPacketApproval?: {
    eligible: boolean;
    reason: string;
    decisions?: Array<"approve-once" | "deny">;
    latestDecision?: {
      id: string;
      decision: string;
      createdAt: string;
      actor: string;
      queuedPacket?: string;
    };
    followupJob?: {
      job_id: string;
      state: string;
      owner: string;
      objective: string;
    } | null;
  };
};

export type QueueRequestStatus =
  | "queued"
  | "refresh_delayed"
  | "failed"
  | "completed"
  | "acknowledged";

export type QueueRequest = {
  id: string;
  jobId: string;
  owner: "POLARIS";
  status: QueueRequestStatus;
  message: string;
  intakePath: string;
  packetNumber?: number;
  createdAt: string;
};

export type InboxPayload = {
  counts: Record<string, number>;
  updatedTs: number | null;
  approvals: ApprovalItem[];
  jobs: JobItem[];
  blockedJobs: JobItem[];
  pendingVerificationJobs: JobItem[];
  queueRequests: QueueRequest[];
};

export type HomePayload = {
  today: string;
  review: string;
  approvalsCount: number;
  pendingApprovals: ApprovalItem[];
  jobCounts: Record<string, number>;
  jobs: JobItem[];
  updatedTs: number | null;
  updatedAt?: string | null;
};

export type ReviewPayload = {
  today: string;
  followups: string;
  review: string;
};

export type ControlDeckTone = "good" | "warn" | "alert" | "neutral";

export type HealthSignal = {
  id: string;
  label: string;
  status: string;
  tone?: ControlDeckTone;
  detail?: string | null;
  value?: string | number | boolean | null;
  updatedAt?: string | null;
  nextStep?: string | null;
};

export type RepoSignal = {
  id: string;
  name: string;
  path: string;
  branch?: string | null;
  status: string;
  tone?: ControlDeckTone;
  dirty?: boolean;
  ahead?: number;
  behind?: number;
  detail?: string | null;
  updatedAt?: string | null;
};

export type LaunchAgentSignal = {
  id: string;
  label: string;
  status: string;
  tone?: ControlDeckTone;
  loaded?: boolean;
  running?: boolean;
  pid?: number | null;
  lastExitStatus?: number | null;
  detail?: string | null;
  updatedAt?: string | null;
};

export type CleanupCandidate = {
  id: string;
  label: string;
  kind: string;
  path?: string | null;
  description?: string | null;
  sizeBytes?: number | null;
  risk?: "low" | "medium" | "high";
  selected?: boolean;
  preview?: string | null;
};

export type ActionDescriptor = {
  id: string;
  title: string;
  lane: "overview" | "orion" | "workstation" | "repos" | "cleanup" | "activity" | string;
  description?: string | null;
  risk?: "low" | "medium" | "high";
  requiresApproval?: boolean;
  enabled?: boolean;
  unavailableReason?: string | null;
};

export type ActionPreview = {
  actionId: string;
  previewId?: string | null;
  title: string;
  summary: string;
  risk?: "low" | "medium" | "high";
  requiresApproval?: boolean;
  blocked?: boolean;
  blockedReason?: string | null;
  candidates?: CleanupCandidate[];
  changes?: string[];
  commands?: string[];
  restoreAvailable?: boolean;
  expiresAt?: string | null;
};

export type ActionRun = {
  actionId: string;
  runId: string;
  status: "queued" | "running" | "succeeded" | "failed" | "blocked";
  message: string;
  previewId?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  restoreToken?: string | null;
  output?: string[];
};

export type AuditEvent = {
  id: string;
  at: string;
  type: string;
  title: string;
  detail?: string | null;
  actionId?: string | null;
  actor?: string | null;
  status?: "succeeded" | "failed" | "blocked" | "pending" | string;
};

export type ControlDeckSnapshot = {
  generatedAt: string | null;
  verdict: {
    title: string;
    summary: string;
    tone: ControlDeckTone;
    updatedAt?: string | null;
  };
  attentionItems: HealthSignal[];
  workstation: HealthSignal[];
  orion: HealthSignal[];
  repos: RepoSignal[];
  launchAgents: LaunchAgentSignal[];
  cleanup: CleanupCandidate[];
  activity: AuditEvent[];
};
