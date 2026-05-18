// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MiniApp } from "./app";
import type {
  ActionDescriptor,
  ActionPreview,
  ActionRun,
  BootstrapPayload,
  ControlDeckSnapshot,
  HomePayload,
  InboxPayload,
  ReviewPayload,
} from "./types";
import { screenFromStartapp } from "./view-model";

const conversation = {
  conversationId: "miniapp-local",
  sessionId: "session-local",
  updatedAt: Date.now(),
  messages: [],
};

function createApi(overrides: Record<string, unknown> = {}) {
  const bootstrap: BootstrapPayload = {
    appName: "Mac Mini Control Deck",
    startapp: "deck",
    user: { id: 1, first_name: "Cory" },
    hasQueryId: false,
    operatorIdsConfigured: true,
    conversation,
  };
  const home: HomePayload = {
    today: "Today is clear.",
    review: "Review is clear.",
    approvalsCount: 0,
    pendingApprovals: [],
    jobCounts: {},
    jobs: [],
    updatedTs: Date.now(),
  };
  const review: ReviewPayload = {
    today: "Today is clear.",
    followups: "No followups.",
    review: "Review is clear.",
  };
  const inbox: InboxPayload = {
    counts: {},
    updatedTs: Date.now(),
    approvals: [],
    jobs: [
      {
        job_id: "job-1",
        state: "blocked",
        owner: "POLARIS",
        objective: "Review a blocked packet.",
      },
    ],
    blockedJobs: [],
    pendingVerificationJobs: [],
    queueRequests: [],
  };
  const snapshot: ControlDeckSnapshot = {
    generatedAt: new Date().toISOString(),
    verdict: {
      title: "Mac Mini is steady",
      summary: "No urgent workstation issues.",
      tone: "good",
    },
    attentionItems: [
      {
        id: "disk",
        label: "Data Volume",
        status: "87% used",
        tone: "warn",
        detail: "Disk is getting tight.",
      },
    ],
    workstation: [
      {
        id: "tool-openclaw",
        label: "openclaw",
        status: "2026.5.12",
        tone: "good",
        detail: "OpenClaw 2026.5.12",
      },
    ],
    orion: [
      {
        id: "gateway",
        label: "Gateway",
        status: "running",
        tone: "good",
        detail: "LaunchAgent is active.",
      },
    ],
    repos: [
      {
        id: "repo-orion",
        name: "ORION",
        path: "/Users/corystoner/src/ORION",
        branch: "main",
        status: "clean",
        tone: "good",
        dirty: false,
      },
    ],
    launchAgents: [
      {
        id: "agent-miniapp",
        label: "com.openclaw.orion.miniapp",
        status: "running",
        tone: "good",
        loaded: true,
        running: true,
      },
    ],
    cleanup: [
      {
        id: "cleanup-one",
        label: "Generated preview cache",
        kind: "cache",
        path: "/tmp/generated",
        description: "Fixture cleanup candidate.",
        sizeBytes: 2048,
        risk: "low",
      },
    ],
    activity: [],
  };
  const actions: ActionDescriptor[] = [
    {
      id: "preview-cleanup",
      title: "Preview Cleanup",
      lane: "cleanup",
      risk: "low",
      requiresApproval: false,
      enabled: true,
    },
    {
      id: "quarantine-cleanup",
      title: "Quarantine Cleanup",
      lane: "cleanup",
      risk: "medium",
      requiresApproval: true,
      enabled: true,
    },
  ];
  const preview: ActionPreview = {
    actionId: "preview-cleanup",
    title: "Preview Cleanup",
    summary: "No files will move.",
    risk: "low",
    requiresApproval: false,
    candidates: snapshot.cleanup,
    changes: ["Generated preview cache: 2048 bytes"],
  };
  const run: ActionRun = {
    actionId: "quarantine-cleanup",
    runId: "run-1",
    status: "succeeded",
    message: "1 item moved into quarantine.",
    output: ["Generated preview cache moved."],
    restoreToken: "quarantine-one",
  };
  return {
    bootstrap: vi.fn(async () => bootstrap),
    home: vi.fn(async () => home),
    review: vi.fn(async () => review),
    inbox: vi.fn(async () => inbox),
    controlDeckSnapshot: vi.fn(async () => snapshot),
    controlDeckActions: vi.fn(async () => ({ actions })),
    controlDeckAudit: vi.fn(async () => ({ events: [] })),
    previewControlDeckAction: vi.fn(async () => preview),
    approveControlDeckAction: vi.fn(async () => run),
    restoreControlDeckAction: vi.fn(async () => run),
    fetchJobDetail: vi.fn(),
    sendChat: vi.fn(async () => ({
      runId: "run-chat",
      conversationId: conversation.conversationId,
      sessionId: conversation.sessionId,
      status: "completed",
      createdAt: Date.now(),
      events: [],
      conversation,
      lastMessage: "Sent.",
    })),
    resolveApproval: vi.fn(),
    resolveTaskPacketApproval: vi.fn(),
    createFollowup: vi.fn(async () => ({ message: "Follow-up queued." })),
    updateQueueRequestStatus: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Mac Mini Control Deck app", () => {
  it("routes deck start params to the Control Deck", () => {
    expect(screenFromStartapp("deck")).toBe("deck");
    expect(screenFromStartapp("mac-mini")).toBe("deck");
  });

  it("renders the control deck verdict and lanes", async () => {
    render(<MiniApp api={createApi() as any} />);

    expect(await screen.findByRole("heading", { name: "Mac Mini is steady" })).toBeInTheDocument();
    expect(screen.getByText("Data Volume")).toBeInTheDocument();
    expect(screen.getByText("Gateway")).toBeInTheDocument();
    expect(screen.getByText("Generated preview cache")).toBeInTheDocument();
  });

  it("previews cleanup before quarantine", async () => {
    const api = createApi();
    render(<MiniApp api={api as any} />);

    await screen.findByRole("heading", { name: "Mac Mini is steady" });
    fireEvent.click(screen.getByLabelText(/Generated preview cache/i));
    fireEvent.click(screen.getByRole("button", { name: "Preview Selected" }));

    await waitFor(() => expect(api.previewControlDeckAction).toHaveBeenCalledWith("preview-cleanup", expect.objectContaining({ candidateIds: ["cleanup-one"] })));
    expect(await screen.findByText("No files will move.")).toBeInTheDocument();
  });

  it("uses the quarantine item token when restoring the last cleanup run", async () => {
    const restored: ActionRun = {
      actionId: "restore-quarantine",
      runId: "restore-1",
      status: "succeeded",
      message: "Restored from quarantine.",
      output: ["Generated preview cache restored."],
    };
    const api = createApi({
      restoreControlDeckAction: vi.fn(async () => restored),
    });
    render(<MiniApp api={api as any} />);

    await screen.findByRole("heading", { name: "Mac Mini is steady" });
    fireEvent.click(screen.getByLabelText(/Generated preview cache/i));
    fireEvent.click(screen.getByRole("button", { name: "Quarantine Selected" }));

    await waitFor(() => expect(screen.getAllByText("1 item moved into quarantine.").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Restore Last Run" }));

    await waitFor(() =>
      expect(api.restoreControlDeckAction).toHaveBeenCalledWith(
        "quarantine-cleanup",
        expect.objectContaining({ itemId: "quarantine-one" })
      )
    );
    await waitFor(() => expect(screen.getAllByText("Restored from quarantine.").length).toBeGreaterThan(0));
  });

  it("redacts secret-looking backend errors in the UI", async () => {
    const api = createApi({
      createFollowup: vi.fn(async () => {
        throw new Error("token=super-secret-value leaked from backend");
      }),
    });
    render(<MiniApp api={api as any} />);

    await screen.findByRole("heading", { name: "Mac Mini is steady" });
    fireEvent.click(screen.getByRole("button", { name: "Task Queue" }));
    fireEvent.click(await screen.findByRole("button", { name: "Follow Up" }));

    expect(await screen.findByText("Follow-up failed.")).toBeInTheDocument();
    expect(screen.queryByText(/super-secret-value/i)).not.toBeInTheDocument();
  });
});
