// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MiniAppView } from "./app";
import { screenFromStartapp } from "./view-model";

describe("mini app view model", () => {
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
        screenLabel="Bridge Chat"
        connectionPill="Bridge ready"
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
        loading={false}
        error=""
        composerText="Draft prompt"
        sending={true}
        activityText="Routing to ORION..."
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
      />
    );

    expect(screen.getByText("Ready on the bridge.")).toBeInTheDocument();
    expect(screen.getByText("Summarize my queue.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Draft prompt")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();
  });

  it("disables the composer when chat bootstrap has not produced a conversation", () => {
    render(
      <MiniAppView
        appName="ORION"
        screen="chat"
        screenLabel="Bridge Chat"
        connectionPill="Bridge ready"
        conversation={null}
        inbox={null}
        home={null}
        review={null}
        loading={false}
        error=""
        composerText="Hello?"
        sending={false}
        activityText="Bridge stable"
        actionMessage=""
        selectedJobId={null}
        onScreenChange={vi.fn()}
        onComposerChange={vi.fn()}
        onComposerSubmit={vi.fn()}
        onApproval={vi.fn()}
        onFollowup={vi.fn()}
        onSelectJob={vi.fn()}
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
        connectionPill="Bridge ready"
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
        }}
        home={null}
        review={null}
        loading={false}
        error=""
        composerText=""
        sending={false}
        activityText="Bridge stable"
        actionMessage=""
        selectedJobId={null}
        onScreenChange={noop}
        onComposerChange={noop}
        onComposerSubmit={noop}
        onApproval={noop}
        onFollowup={noop}
        onSelectJob={noop}
      />
    );

    expect(screen.getByText("Mission Inbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Allow Once" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Queue Follow-Up" })).toBeInTheDocument();

    rerender(
      <MiniAppView
        appName="ORION"
        screen="today"
        screenLabel="Today"
        connectionPill="Bridge ready"
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
        loading={false}
        error=""
        composerText=""
        sending={false}
        activityText="Bridge stable"
        actionMessage=""
        selectedJobId={null}
        onScreenChange={noop}
        onComposerChange={noop}
        onComposerSubmit={noop}
        onApproval={noop}
        onFollowup={noop}
        onSelectJob={noop}
      />
    );

    expect(screen.getByText("Follow-Ups")).toBeInTheDocument();
    expect(screen.getByText(/Follow up with POLARIS/)).toBeInTheDocument();
  });
});
