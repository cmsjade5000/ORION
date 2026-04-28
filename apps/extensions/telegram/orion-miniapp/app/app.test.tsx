// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MiniApp, MiniAppView } from "./app";
import type { BootstrapPayload, ChatConversation, HomePayload, InboxPayload, ReviewPayload } from "./types";
import { screenFromStartapp } from "./view-model";

describe("mini app view model", () => {
  const bridgeStatus = { label: "Bridge online", tone: "good" as const };

  const conversation: ChatConversation = {
    conversationId: "miniapp-1-main",
    sessionId: "miniapp-session-1",
    updatedAt: Date.now(),
    messages: [{ id: "m1", role: "assistant", text: "Ready on the bridge.", createdAt: Date.now() }],
  };

  const bootstrapPayload: BootstrapPayload = {
    appName: "ORION",
    startapp: "home",
    user: { id: 1, first_name: "Cory" },
    hasQueryId: false,
    operatorIdsConfigured: true,
    conversation,
  };

  const homePayload: HomePayload = {
    today: "Open delegated work:\n- ATLAS: Check the queue.",
    review: "Review digest",
    approvalsCount: 1,
    pendingApprovals: [],
    jobCounts: {},
    jobs: [],
    updatedTs: Date.now(),
  };

  const reviewPayload: ReviewPayload = {
    today: "Today digest",
    followups: "Follow up with POLARIS",
    review: "Review digest",
  };

  const inboxPayload: InboxPayload = {
    counts: { blocked: 1, pending_verification: 1 },
    updatedTs: Date.now(),
    approvals: [
      {
        approvalId: "abc",
        suggestedDecision: "allow-once",
        summary: "Need approval for a bounded action.",
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
        state: "blocked",
        owner: "ATLAS",
        objective: "Check the queue.",
        inbox: { path: "tasks/INBOX/ATLAS.md", line: 12 },
      },
    ],
    blockedJobs: [
      {
        job_id: "job-1",
        state: "blocked",
        owner: "ATLAS",
        objective: "Check the queue.",
      },
    ],
    pendingVerificationJobs: [],
    queueRequests: [],
  };

  function createApi() {
    return {
      bootstrap: vi.fn(async () => bootstrapPayload),
      home: vi.fn(async () => homePayload),
      review: vi.fn(async () => reviewPayload),
      inbox: vi.fn(async () => inboxPayload),
      sendChat: vi.fn(),
      fetchRun: vi.fn(),
      streamRun: vi.fn(() => vi.fn()),
      resolveApproval: vi.fn(),
      createFollowup: vi.fn(),
      updateQueueRequestStatus: vi.fn(),
    };
  }

  function createTelegramButtonStub() {
    const callbacks = new Set<() => void>();
    return {
      callbacks,
      show: vi.fn(),
      hide: vi.fn(),
      enable: vi.fn(),
      disable: vi.fn(),
      setText: vi.fn(),
      showProgress: vi.fn(),
      hideProgress: vi.fn(),
      onClick: vi.fn((callback: () => void) => callbacks.add(callback)),
      offClick: vi.fn((callback: () => void) => callbacks.delete(callback)),
      trigger: () => {
        callbacks.forEach((callback) => callback());
      },
    };
  }

  function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  }

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    delete window.Telegram;
  });

  it("maps legacy startapp values onto the new screens", () => {
    expect(screenFromStartapp("home")).toBe("chat");
    expect(screenFromStartapp("approvals")).toBe("inbox");
    expect(screenFromStartapp("review")).toBe("today");
  });

  it("renders the chat transcript and composer state", () => {
    render(
      <MiniAppView
        appName="ORION"
        screen="chat"
        screenLabel="Chat"
        bridgeStatus={bridgeStatus}
        conversation={{
          conversationId: "miniapp-1-main",
          sessionId: "miniapp-session-1",
          updatedAt: Date.now(),
          messages: [
            { id: "m1", role: "assistant", text: "Ready on the bridge.", createdAt: Date.now() },
            { id: "m2", role: "user", text: "Summarize my queue.", createdAt: Date.now() },
          ],
        }}
        inbox={null}
        home={null}
        review={null}
        queueRequests={[]}
        loading={false}
        error=""
        composerText="Draft prompt"
        sending={true}
        hasNativeMainButton={false}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
        onQueueCenter={vi.fn()}
      />
    );

    expect(screen.getByText("Ready on the bridge.")).toBeInTheDocument();
    expect(screen.getByText("Summarize my queue.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Draft prompt")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();
  });

  it("hides the in-app chat send button when Telegram MainButton is available", () => {
    render(
      <MiniAppView
        appName="ORION"
        screen="chat"
        screenLabel="Chat"
        bridgeStatus={bridgeStatus}
        conversation={conversation}
        inbox={null}
        home={null}
        review={null}
        queueRequests={[]}
        loading={false}
        error=""
        composerText="Send this"
        sending={false}
        hasNativeMainButton={true}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
        onQueueCenter={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("Send this")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send to ORION" })).not.toBeInTheDocument();
  });

  it("keeps normal in-app navigation from re-running bootstrap back to home", async () => {
    const fetchCalls: string[] = [];
    const responseFor = (pathname: string) => {
      if (pathname === "/api/bootstrap") return bootstrapPayload;
      if (pathname === "/api/home") return homePayload;
      if (pathname === "/api/review") return reviewPayload;
      if (pathname === "/api/inbox") return inboxPayload;
      return {};
    };
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(rawUrl, "http://localhost").pathname;
      fetchCalls.push(pathname);
      return new Response(JSON.stringify(responseFor(pathname)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    render(<MiniApp />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    expect(fetchCalls.filter((path) => path === "/api/bootstrap")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /Today/ }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(fetchCalls.filter((path) => path === "/api/bootstrap")).toHaveLength(1);
  });

  it("keeps Telegram BackButton handling separate from normal app buttons", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();
    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: { selectionChanged: vi.fn(), notificationOccurred: vi.fn(), impactOccurred: vi.fn() },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Today/ }));

    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);
    expect(mainButton.callbacks.size).toBe(0);

    fireEvent.click(screen.getByRole("button", { name: /Mission Inbox/ }));
    expect(screen.getByRole("heading", { name: "Mission Inbox" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    expect(screen.getByRole("heading", { name: "Selected Work Item" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    act(() => {
      backButton.trigger();
    });
    expect(screen.getByRole("heading", { name: "Mission Inbox" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Queue Notes" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /Today/ }));
    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(1);

    act(() => {
      backButton.trigger();
    });
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
    expect(backButton.callbacks.size).toBe(0);
  });

  it("does not re-register the Telegram MainButton while typing", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();
    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: { selectionChanged: vi.fn(), notificationOccurred: vi.fn(), impactOccurred: vi.fn() },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    const setTextCalls = mainButton.setText.mock.calls.length;
    const showCalls = mainButton.show.mock.calls.length;
    const hideCalls = mainButton.hide.mock.calls.length;
    const onClickCalls = mainButton.onClick.mock.calls.length;
    const offClickCalls = mainButton.offClick.mock.calls.length;

    const composer = screen.getByPlaceholderText("Message ORION from the bridge...");
    fireEvent.change(composer, { target: { value: "H" } });
    fireEvent.change(composer, { target: { value: "He" } });
    fireEvent.change(composer, { target: { value: "Hey" } });

    expect(mainButton.setText).toHaveBeenCalledTimes(setTextCalls);
    expect(mainButton.show).toHaveBeenCalledTimes(showCalls);
    expect(mainButton.hide).toHaveBeenCalledTimes(hideCalls);
    expect(mainButton.onClick).toHaveBeenCalledTimes(onClickCalls);
    expect(mainButton.offClick).toHaveBeenCalledTimes(offClickCalls);
    expect(mainButton.enable).toHaveBeenCalledTimes(1);
  });

  it("uses Telegram MainButton to queue a selected work item once", async () => {
    const api = createApi();
    const mainButton = createTelegramButtonStub();
    const backButton = createTelegramButtonStub();
    const followup = deferred<Awaited<ReturnType<typeof api.createFollowup>>>();
    api.createFollowup.mockReturnValue(followup.promise);
    const followupPayload = {
      message: "Captured for POLARIS.",
      request: {
        id: "qr-1",
        jobId: "job-1",
        owner: "POLARIS",
        status: "queued",
        message: "Captured for POLARIS.",
        intakePath: "tasks/INTAKE/example.md",
        packetNumber: 5,
        createdAt: "2026-04-28T13:00:00.000Z",
      },
    };
    window.Telegram = {
      WebApp: {
        MainButton: mainButton,
        BackButton: backButton,
        ready: vi.fn(),
        expand: vi.fn(),
        HapticFeedback: { selectionChanged: vi.fn(), notificationOccurred: vi.fn(), impactOccurred: vi.fn() },
      },
    };

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Mission Inbox/ }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));

    expect(mainButton.setText).toHaveBeenLastCalledWith("Queue Follow-Up");
    act(() => {
      mainButton.trigger();
      mainButton.trigger();
    });
    expect(api.createFollowup).toHaveBeenCalledTimes(1);

    await act(async () => {
      followup.resolve(followupPayload);
      await followup.promise;
    });

    expect(await screen.findAllByText("Follow-Up Queued")).not.toHaveLength(0);
    expect(api.createFollowup).toHaveBeenCalledTimes(1);

    const queuedButtons = screen.getAllByRole("button", { name: "Follow-Up Queued" });
    fireEvent.click(queuedButtons[0]);
    expect(api.createFollowup).toHaveBeenCalledTimes(1);
  });

  it("keeps raw follow-up backend errors out of the queue UI", async () => {
    const api = createApi();
    api.createFollowup.mockRejectedValueOnce(new Error("ENOENT: open /Users/corystoner/.openclaw/secrets/raw-token"));

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Mission Inbox/ }));
    fireEvent.click(screen.getByRole("button", { name: "Queue Follow-Up" }));

    expect(await screen.findByText("Follow-up action failed.")).toBeInTheDocument();
    expect(screen.queryByText(/ENOENT/)).not.toBeInTheDocument();
    expect(screen.queryByText(/raw-token/)).not.toBeInTheDocument();
  });

  it("keeps follow-up success visible when the follow-up refresh fails", async () => {
    const api = createApi();
    api.home
      .mockResolvedValueOnce(homePayload)
      .mockRejectedValueOnce(
        new Error(
          "Command failed: python3 scripts/assistant_status.py --repo-root /Users/corystoner/src/ORION --cmd routing --json"
        )
      );
    api.createFollowup.mockResolvedValueOnce({
      message: "Captured for POLARIS.\n- Intake: tasks/INTAKE/example.md\n- POLARIS packet queued: #5",
    });

    render(<MiniApp api={api} />);

    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Mission Inbox/ }));
    fireEvent.click(screen.getByRole("button", { name: "Queue Follow-Up" }));

    expect(await screen.findAllByText(/Queued; Refresh Delayed/)).not.toHaveLength(0);
    expect(screen.queryByText(/Command failed:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/assistant_status\.py/)).not.toBeInTheDocument();
  });

  it("disables the composer when chat bootstrap has not produced a conversation", () => {
    render(
      <MiniAppView
        appName="ORION"
        screen="chat"
        screenLabel="Chat"
        bridgeStatus={bridgeStatus}
        conversation={null}
        inbox={null}
        home={null}
        review={null}
        queueRequests={[]}
        loading={false}
        error=""
        composerText="Hello?"
        sending={false}
        hasNativeMainButton={false}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
        onQueueCenter={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("Hello?")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send to ORION" })).toBeDisabled();
  });

  it("renders inbox actions and today panels", () => {
    const noop = vi.fn();
    const { rerender } = render(
      <MiniAppView
        appName="ORION"
        screen="inbox"
        screenLabel="Mission Inbox"
        bridgeStatus={bridgeStatus}
        conversation={null}
        inbox={{
          counts: { blocked: 1, pending_verification: 1 },
          updatedTs: Date.now(),
          approvals: [
            {
              approvalId: "abc",
              suggestedDecision: "allow-once",
              summary: "Need approval for a bounded action.",
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
              state: "blocked",
              owner: "ATLAS",
              objective: "Check the queue.",
              inbox: { path: "tasks/INBOX/ATLAS.md", line: 12 },
            },
          ],
          blockedJobs: [
            {
              job_id: "job-1",
              state: "blocked",
              owner: "ATLAS",
              objective: "Check the queue.",
            },
          ],
          pendingVerificationJobs: [],
          queueRequests: [],
        }}
        home={null}
        review={null}
        queueRequests={[]}
        loading={false}
        error=""
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={noop}
        onComposerChange={noop}
        onComposerSubmit={noop}
        onApproval={noop}
        onFollowup={noop}
        onSelectJob={noop}
        onQueueCenter={noop}
      />
    );

    expect(screen.getByRole("heading", { name: "Mission Inbox" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Allow Once" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Queue Follow-Up" })).toBeInTheDocument();

    rerender(
      <MiniAppView
        appName="ORION"
        screen="today"
        screenLabel="Today"
        bridgeStatus={bridgeStatus}
        conversation={null}
        inbox={null}
        home={{
          today: "Open delegated work:\n- ATLAS: Check the queue.",
          review: "Review digest",
          approvalsCount: 1,
          pendingApprovals: [],
          jobCounts: {},
          jobs: [],
          updatedTs: Date.now(),
        }}
        review={{
          today: "Today digest",
          followups: "Follow up with POLARIS",
          review: "Review digest",
        }}
        queueRequests={[]}
        loading={false}
        error=""
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={noop}
        onComposerChange={noop}
        onComposerSubmit={noop}
        onApproval={noop}
        onFollowup={noop}
        onSelectJob={noop}
        onQueueCenter={noop}
      />
    );

    expect(screen.getByText("Follow-Ups")).toBeInTheDocument();
    expect(screen.getByText(/Follow up with POLARIS/)).toBeInTheDocument();
  });

  it("renders queue center records with intake details", () => {
    render(
      <MiniAppView
        appName="ORION"
        screen="queue"
        screenLabel="Queue Center"
        bridgeStatus={bridgeStatus}
        conversation={null}
        inbox={null}
        home={null}
        review={null}
        queueRequests={[
          {
            id: "qr-1",
            jobId: "job-1",
            owner: "POLARIS",
            status: "queued",
            message: "Captured for POLARIS.",
            intakePath: "tasks/INTAKE/example.md",
            packetNumber: 5,
            createdAt: "2026-04-28T13:00:00.000Z",
          },
        ]}
        loading={false}
        error=""
        composerText=""
        sending={false}
        hasNativeMainButton={false}
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
        onQueueCenter={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { name: "Queue Center" })).toBeInTheDocument();
    expect(screen.getByText("Captured for POLARIS.")).toBeInTheDocument();
    expect(screen.getByText("tasks/INTAKE/example.md")).toBeInTheDocument();
  });
});
