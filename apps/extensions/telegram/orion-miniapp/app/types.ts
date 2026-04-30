export type MiniAppScreen = "chat" | "inbox" | "today" | "queue";

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
};

export type QueueRequestStatus = "queued" | "refresh_delayed" | "failed";

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
};

export type ReviewPayload = {
  today: string;
  followups: string;
  review: string;
};
