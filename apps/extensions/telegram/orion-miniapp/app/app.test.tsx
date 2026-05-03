// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MiniApp, MiniAppView } from "./app";
import type { BootstrapPayload, ChatConversation, HomePayload, InboxPayload, QueueRequest, ReviewPayload } from "./types";
import { parseTaskIdFromStartapp, screenFromStartapp } from "./view-model";

type TelegramButtonStub = {
  callbacks: Set<() => void>;
  show: () => void;
  hide: () => void;
  enable: () => void;
  disable: () => void;
  setText: (text: string) => void;
  showProgress?: (leaveActive?: boolean) => void;
  hideProgress?: () => void;
  onClick: (callback: () => void) => void;
  offClick: (callback: () => void) => void;
  trigger: () => void;
};

function createTelegramButtonStub() {
  const callbacks = new Set<() => void>();
  return {
    callbacks,
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
    setText: vi.fn(),
    showProgress: vi.fn((leaveActive?: boolean) => leaveActive),
    hideProgress: vi.fn(),
    onClick: vi.fn((callback: () => void) => {
      callbacks.add(callback);
    }),
    offClick: vi.fn((callback: () => void) => {
      callbacks.delete(callback);
    }),
    trigger: () => {
      callbacks.forEach((callback) => callback());
    },
  } as TelegramButtonStub;
}

function createApi() {
  const bootstrapPayload: BootstrapPayload = {
    appName: "ORION",
    startapp: "home",
    user: { id: 1, first_name: "Cory" },
    hasQueryId: false,
    operatorIdsConfigured: true,
    conversation: {
      conversationId: "miniapp-1-main",
      sessionId: "miniapp-session-1",
      updatedAt: Date.now(),
      messages: [
        {
          id: "m1",
          role: "assistant",
          text: "Ready on the bridge.",
          createdAt: Date.now(),
        },
      ],
    },
  };

  const homePayload: HomePayload = {
    today: "Ready on bridge.",
    review: "Review digest",
    approvalsCount: 1,
    pendingApprovals: [],
    jobCounts: {},
    jobs: [],
    updatedTs: Date.now(),
  };

  const reviewPayload: ReviewPayload = {
    today: "Today digest",
    followups: "Need follow-ups",
    review: "Review digest",
  };

  const inboxPayload: InboxPayload = {
    counts: { blocked: 1, pending_verification: 0 },
    updatedTs: Date.now(),
    approvals: [
      {
        approvalId: "abc",
        suggestedDecision: "allow-once",
        summary: "Need approval for bounded action.",
        label: "approval",
        sessionId: "s1",
        sessionKey: "k1",
        ts: Date.now(),
        ageMs: 120000,
      },
    ],
    jobs: [
      {
        job_id: "job-1",
        state: "running",
        owner: "POLARIS",
        objective: "Check ORION queue depth.",
        inbox: { path: "tasks/INBOX/POLARIS.md", line: 3 },
      },
      {
        job_id: "job-2",
        state: "blocked",
        owner: "POLARIS",
        objective: "Needs human input on policy selection.",
      },
    ],
    blockedJobs: [
      {
        job_id: "job-2",
        state: "blocked",
        owner: "POLARIS",
        objective: "Needs human input on policy selection.",
      },
    ],
    pendingVerificationJobs: [],
    queueRequests: [
      {
        id: "qr-1",
        jobId: "job-1",
        owner: "POLARIS",
        status: "completed",
        message: "Initial request complete.",
        intakePath: "tasks/INTAKE/one.md",
        packetNumber: 1,
        createdAt: new Date().toISOString(),
      },
    ],
  };

  return {
    bootstrap: vi.fn(async () => bootstrapPayload),
    home: vi.fn(async () => homePayload),
    review: vi.fn(async () => reviewPayload),
    inbox: vi.fn(async () => inboxPayload),
    fetchJobDetail: vi.fn(async (jobId: string) => ({
      job: inboxPayload.jobs.find((job) => job.job_id === jobId) || inboxPayload.jobs[0],
      needSummary: "Approval waiting on an external signal.",
      nextStep: "Wait for approval or provide follow-up.",
      packetText: "TASK_PACKET v1",
      resultLines: ["Status: BLOCKED", "Needs input."],
      relatedApprovals: inboxPayload.approvals,
      taskPacketApproval: {
        eligible: true,
        reason: "Approve once to continue this request.",
        decisions: ["approve-once", "deny"] as Array<"approve-once" | "deny">,
      },
    })),
    sendChat: vi.fn(async () => ({
      runId: "run-1",
      conversationId: "miniapp-1-main",
      sessionId: "miniapp-session-1",
      status: "completed",
      createdAt: Date.now(),
      conversation: {
        conversationId: "miniapp-1-main",
        sessionId: "miniapp-session-1",
        updatedAt: Date.now(),
        messages: [
          {
            id: "m2",
            role: "user",
            text: "Hello Orion",
            createdAt: Date.now(),
          },
        ],
      },
      events: [],
    } as any)),
    fetchRun: vi.fn(async () => ({
      runId: "run-1",
      conversationId: "miniapp-1-main",
      sessionId: "miniapp-session-1",
      status: "completed",
      createdAt: Date.now(),
      conversation: {
        conversationId: "miniapp-1-main",
        sessionId: "miniapp-session-1",
        updatedAt: Date.now(),
        messages: [
          {
            id: "m2",
            role: "user",
            text: "Hello Orion",
            createdAt: Date.now(),
          },
        ],
      },
      events: [],
    } as any)),
    streamRun: vi.fn(() => vi.fn()),
    resolveApproval: vi.fn(async () => ({ message: "Approval recorded" })),
    resolveTaskPacketApproval: vi.fn(async () => ({ message: "Decision applied" })),
    createFollowup: vi.fn(async () => {
      const request: QueueRequest = {
        id: `qr-${Date.now()}`,
        jobId: "job-2",
        owner: "POLARIS",
        status: "queued",
        message: "Rework queued.",
        intakePath: "tasks/INTAKE/rework.md",
        packetNumber: 2,
        createdAt: new Date().toISOString(),
      };
      return { message: "Rework queued", request };
    }),
    updateQueueRequestStatus: vi.fn(async (requestId: string) => {
      const request: QueueRequest = {
        id: requestId,
        jobId: "job-1",
        owner: "POLARIS",
        status: "acknowledged",
        message: "Queue packet acknowledged.",
        intakePath: "tasks/INTAKE/one.md",
        createdAt: new Date().toISOString(),
      };
      return { request };
    }),
  };
}

function makeConversation(): ChatConversation {
  return {
    conversationId: "miniapp-1-main",
    sessionId: "miniapp-session-1",
    updatedAt: Date.now(),
    messages: [{ id: "m1", role: "assistant", text: "Ready.", createdAt: Date.now() }],
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  delete window.Telegram;
});

describe("ORION Relay Console route model", () => {
  it("maps deep-link screens through screenFromStartapp", () => {
    expect(screenFromStartapp("home")).toBe("home");
    expect(screenFromStartapp("queue")).toBe("queue");
    expect(screenFromStartapp("compose")).toBe("compose");
    expect(screenFromStartapp("activity")).toBe("activity");
    expect(screenFromStartapp("feed")).toBe("activity");
    expect(screenFromStartapp("settings")).toBe("settings");
    expect(screenFromStartapp("task/job-1")).toBe("task");
    expect(screenFromStartapp("status")).toBe("status");
  });

  it("preserves task-id casing when parsing startapp task links", () => {
    expect(parseTaskIdFromStartapp("task:AbC123")).toBe("AbC123");
    expect(parseTaskIdFromStartapp("task/Ab-C_123")).toBe("Ab-C_123");
  });

  it("renders the command-center and quick request cards", () => {
    render(
      <MiniAppView
        appName="ORION"
        route={{ screen: "home" }}
        routeDepth={1}
        bridgeStatus={{ label: "Bridge online", tone: "good" }}
        canGoBack={false}
        loading={false}
        error=""
        actionMessage=""
        conversation={makeConversation()}
        inbox={null}
        home={null}
        review={null}
        tasks={[]}
        queueFilter="active"
        queueRequests={[]}
        activity={[]}
        systemStatus={{
          api: "online",
          queue: "healthy",
          worker: "healthy",
          updatedAt: new Date().toISOString(),
          message: "Live state is available.",
        }}
        selectedJobDetail={null}
        detailLoading={false}
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        onNavigate={vi.fn()}
        onBack={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onTaskPacketApproval={vi.fn()}
        onFollowup={vi.fn()}
        onAcknowledgeQueueRequest={vi.fn()}
        onOpenTask={vi.fn()}
        onClearError={vi.fn()}
      />,
    );

    expect(screen.getByText("What is Orion doing right now?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New Request" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "System Health" })).toBeInTheDocument();
  });

  it("renders compose as the primary request path", () => {
    render(
      <MiniAppView
        appName="ORION"
        route={{ screen: "compose" }}
        routeDepth={1}
        bridgeStatus={{ label: "Bridge online", tone: "good" }}
        canGoBack={false}
        loading={false}
        error=""
        actionMessage=""
        conversation={makeConversation()}
        inbox={null}
        home={null}
        review={null}
        tasks={[]}
        queueFilter="active"
        queueRequests={[]}
        activity={[]}
        systemStatus={{
          api: "online",
          queue: "healthy",
          worker: "healthy",
          updatedAt: new Date().toISOString(),
          message: "Live state is available.",
        }}
        selectedJobDetail={null}
        detailLoading={false}
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        onNavigate={vi.fn()}
        onBack={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onTaskPacketApproval={vi.fn()}
        onFollowup={vi.fn()}
        onAcknowledgeQueueRequest={vi.fn()}
        onOpenTask={vi.fn()}
        onClearError={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Compose Request" })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send to ORION" })).toBeInTheDocument();
  });

  it("does not bind back behavior to non-navigation buttons", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();

    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: {
          selectionChanged: vi.fn(),
          notificationOccurred: vi.fn(),
          impactOccurred: vi.fn(),
        },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByText("ORION")).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(0);
    expect(backButton.hide).toHaveBeenCalled();
    expect(backButton.show).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Task Queue" }));

    expect(await screen.findByRole("button", { name: "Open Task", hidden: false })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    fireEvent.click(screen.getByRole("tab", { name: "Needs Input" }));
    await waitFor(() => {
      expect(backButton.callbacks.size).toBe(1);
    });
    expect(screen.getByRole("button", { name: "Open Task" })).toBeInTheDocument();

    act(() => {
      backButton.trigger();
    });
    expect(screen.queryByRole("button", { name: "Open Task" })).not.toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(0);
  });

  it("shows Telegram back only on nested route stack and returns to previous context", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();

    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: {
          selectionChanged: vi.fn(),
          notificationOccurred: vi.fn(),
          impactOccurred: vi.fn(),
        },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByText("What is Orion doing right now?" )).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(0);
    expect(backButton.hide).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Task Queue" }));
    expect(await screen.findByRole("button", { name: "Open Task", hidden: false })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);
    expect(backButton.show).toHaveBeenCalled();

    const taskButton = screen.getByText("Open Task");
    fireEvent.click(taskButton);

    expect(await screen.findByText("Task Detail")).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    act(() => {
      backButton.trigger();
    });

    expect(await screen.findByRole("button", { name: "Open Task", hidden: false })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    act(() => {
      backButton.trigger();
    });
    expect(await screen.findByText("What is Orion doing right now?")).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(0);
  });

  it("uses root navigation for top-level tabs so back exits nested root context only", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();

    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: {
          selectionChanged: vi.fn(),
          notificationOccurred: vi.fn(),
          impactOccurred: vi.fn(),
        },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "What is Orion doing right now?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Task Queue" }));
    expect(await screen.findByRole("button", { name: "Open Task", hidden: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "System Status" }));
    expect(await screen.findByRole("heading", { name: "System Status" })).toBeInTheDocument();

    act(() => {
      backButton.trigger();
    });

    expect(await screen.findByRole("heading", { name: "What is Orion doing right now?" })).toBeInTheDocument();
  });

  it("maps last request from home and opens it in one tap", async () => {
    const api = createApi();

    render(<MiniApp api={api} />);

    expect(await screen.findByText("Last request")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Last Request" }));

    expect(await screen.findByText("Task Detail")).toBeInTheDocument();
    expect(screen.getByText("Approval waiting on an external signal." )).toBeInTheDocument();
  });

  it("renders empty queue and error states", async () => {
    const api = createApi();
    api.home.mockResolvedValueOnce({ today: "", review: "", approvalsCount: 0, pendingApprovals: [], jobCounts: {}, jobs: [], updatedTs: Date.now() });
    api.review.mockResolvedValueOnce({ today: "", followups: "", review: "" });
    api.inbox.mockResolvedValueOnce({ counts: {}, updatedTs: Date.now(), approvals: [], jobs: [], blockedJobs: [], pendingVerificationJobs: [], queueRequests: [] });

    render(
      <MiniAppView
        appName="ORION"
        route={{ screen: "queue" }}
        routeDepth={2}
        bridgeStatus={{ label: "Bridge online", tone: "good" }}
        canGoBack={false}
        loading={false}
        error=""
        actionMessage=""
        conversation={makeConversation()}
        inbox={null}
        home={null}
        review={null}
        tasks={[]}
        queueFilter="active"
        queueRequests={[]}
        activity={[]}
        systemStatus={{ api: "partial", queue: "healthy", worker: "healthy", updatedAt: new Date().toISOString(), message: "partial" }}
        selectedJobDetail={null}
        detailLoading={false}
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        onNavigate={vi.fn()}
        onBack={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onTaskPacketApproval={vi.fn()}
        onFollowup={vi.fn()}
        onAcknowledgeQueueRequest={vi.fn()}
        onOpenTask={vi.fn()}
        onClearError={vi.fn()}
      />,
    );

    expect(screen.getByText("No tasks match this filter.")).toBeInTheDocument();

    render(
      <MiniApp
        api={{
          ...api,
          bootstrap: async () => ({
            ...(await api.bootstrap()),
            startapp: "home",
          }),
        }}
      />,
    );

    expect(await screen.findByText("What is Orion doing right now?")).toBeInTheDocument();
  });

  it("shows queue packet acknowledge action for terminal states", async () => {
    const api = createApi();
    const acknowledge = vi.spyOn(api, "updateQueueRequestStatus");

    render(
      <MiniAppView
        appName="ORION"
        route={{ screen: "task", taskId: "job-1" }}
        routeDepth={2}
        bridgeStatus={{ label: "Bridge online", tone: "good" }}
        canGoBack={true}
        loading={false}
        error=""
        actionMessage=""
        conversation={makeConversation()}
        inbox={{
          counts: {},
          updatedTs: Date.now(),
          approvals: [],
          jobs: [
            {
              job_id: "job-1",
              state: "completed",
              owner: "POLARIS",
              objective: "Check queue.",
            },
          ],
          blockedJobs: [],
          pendingVerificationJobs: [],
          queueRequests: [
            {
              id: "qr-1",
              jobId: "job-1",
              owner: "POLARIS",
              status: "completed",
              message: "Task completed.",
              intakePath: "tasks/INTAKE/one.md",
              createdAt: new Date().toISOString(),
            },
          ],
        }}
        home={null}
        review={null}
        tasks={[
          {
            id: "job-1",
            owner: "POLARIS",
            objective: "Check queue.",
            state: "done",
            status: "done",
          },
        ]}
        queueFilter="active"
        queueRequests={[
          {
            id: "qr-1",
            jobId: "job-1",
            owner: "POLARIS",
            status: "completed",
            message: "Task completed.",
            intakePath: "tasks/INTAKE/one.md",
            createdAt: new Date().toISOString(),
          },
        ]}
        activity={[]}
        systemStatus={{ api: "online", queue: "healthy", worker: "healthy", updatedAt: new Date().toISOString(), message: "all good" }}
        selectedJobDetail={{
          job: {
            job_id: "job-1",
            state: "completed",
            owner: "POLARIS",
            objective: "Check queue",
          },
          needSummary: "Done",
          nextStep: "No next step.",
          packetText: "TASK",
          resultLines: ["done"],
          relatedApprovals: [],
          taskPacketApproval: {
            eligible: false,
            reason: "No action",
            decisions: ["deny", "approve-once"] as Array<"approve-once" | "deny">,
          },
        }}
        detailLoading={false}
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        onNavigate={vi.fn()}
        onBack={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onTaskPacketApproval={vi.fn()}
        onFollowup={vi.fn()}
        onAcknowledgeQueueRequest={acknowledge}
        onOpenTask={vi.fn()}
        onClearError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge Packet" }));
    expect(acknowledge).toHaveBeenCalledWith("qr-1");
  });

  it("does not treat task-packet approval taps as back navigation", async () => {
    const onBack = vi.fn();
    const onTaskPacketApproval = vi.fn();

    render(
      <MiniAppView
        appName="ORION"
        route={{ screen: "task", taskId: "job-1" }}
        routeDepth={2}
        bridgeStatus={{ label: "Bridge online", tone: "good" }}
        canGoBack={true}
        loading={false}
        error=""
        actionMessage=""
        conversation={makeConversation()}
        inbox={{
          counts: {},
          updatedTs: Date.now(),
          approvals: [],
          jobs: [
            {
              job_id: "job-1",
              state: "running",
              owner: "POLARIS",
              objective: "Check ORION queue depth.",
            },
          ],
          blockedJobs: [],
          pendingVerificationJobs: [],
          queueRequests: [
            {
              id: "qr-1",
              jobId: "job-1",
              owner: "POLARIS",
              status: "queued",
              message: "Needs review.",
              intakePath: "tasks/INBOX/POLARIS.md",
              createdAt: new Date().toISOString(),
            },
          ],
        }}
        home={null}
        review={null}
        tasks={[
          {
            id: "job-1",
            owner: "POLARIS",
            objective: "Check ORION queue depth.",
            state: "running",
            status: "running",
          },
        ]}
        queueFilter="active"
        queueRequests={[
          {
            id: "qr-1",
            jobId: "job-1",
            owner: "POLARIS",
            status: "queued",
            message: "Needs review.",
            intakePath: "tasks/INBOX/POLARIS.md",
            createdAt: new Date().toISOString(),
          },
        ]}
        activity={[]}
        systemStatus={{ api: "online", queue: "healthy", worker: "healthy", updatedAt: new Date().toISOString(), message: "all good" }}
        selectedJobDetail={{
          job: {
            job_id: "job-1",
            state: "running",
            owner: "POLARIS",
            objective: "Check ORION queue depth.",
          },
          needSummary: "Waiting for action.",
          nextStep: "Use the approval button to continue.",
          packetText: "TASK_PACKET v1",
          resultLines: [],
          relatedApprovals: [],
          taskPacketApproval: {
            eligible: true,
            reason: "Approve once to continue.",
            decisions: ["approve-once", "deny"] as Array<"approve-once" | "deny">,
          },
        }}
        detailLoading={false}
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        onNavigate={vi.fn()}
        onBack={onBack}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onTaskPacketApproval={onTaskPacketApproval}
        onFollowup={vi.fn()}
        onAcknowledgeQueueRequest={vi.fn()}
        onOpenTask={vi.fn()}
        onClearError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve Once" }));
    expect(onBack).not.toHaveBeenCalled();
    expect(onTaskPacketApproval).toHaveBeenCalledWith("job-1", "approve-once");
  });

  it("sends task packet approval action from task detail", async () => {
    const api = createApi();
    const payload = await api.bootstrap();
    const packetDecision = vi.spyOn(api, "resolveTaskPacketApproval");
    api.bootstrap = vi.fn(async () => ({
      ...payload,
      startapp: "task/job-1",
    }));

    render(<MiniApp api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Approve Once" }));
    expect(packetDecision).toHaveBeenCalledWith("job-1", "approve-once");
  });

  it("sends approval decision action from pending approval cards", async () => {
    const api = createApi();
    const bootstrap = await api.bootstrap();
    const approvalDecision = vi.spyOn(api, "resolveApproval");
    const jobDetail = await api.fetchJobDetail("job-1");
    api.bootstrap = vi.fn(async () => ({
      ...bootstrap,
      startapp: "task/job-1",
    }));
    api.fetchJobDetail = vi.fn(async () => ({
      ...jobDetail,
      taskPacketApproval: {
        eligible: false,
        reason: "No task-packet decision needed.",
        decisions: ["approve-once", "deny"] as Array<"approve-once" | "deny">,
      },
    }));

    render(<MiniApp api={api} />);

    fireEvent.click(await screen.findByRole("button", { name: "Allow Once" }));
    expect(approvalDecision).toHaveBeenCalledWith("abc", "allow-once");
  });
});
