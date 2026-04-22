const crypto = require("node:crypto");
const path = require("node:path");
const { spawn } = require("node:child_process");

function now() {
  return Date.now();
}

function randomId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function userFacingRuntimeError(raw) {
  const text = String(raw || "").trim();
  if (!text) return "ORION hit a runtime snag before the bridge replied.";
  if (/timed out/i.test(text)) return "ORION took too long to answer from the bridge path.";
  if (/miniapp-auth/i.test(text)) return "The bridge session expired. Reopen the Mini App from Telegram.";
  return "ORION hit a runtime snag while answering. The bridge is still there; try again.";
}

function serializeConversation(conversation) {
  return {
    conversationId: conversation.conversationId,
    sessionId: conversation.sessionId,
    updatedAt: conversation.updatedAt,
    messages: conversation.messages.map((message) => ({ ...message })),
  };
}

function serializeRun(run, conversation) {
  return {
    runId: run.runId,
    conversationId: run.conversationId,
    sessionId: conversation.sessionId,
    status: run.status,
    createdAt: run.createdAt,
    completedAt: run.completedAt || null,
    error: run.error || null,
    lastMessage: run.lastMessage || null,
    events: run.events.map((event) => ({ ...event })),
    conversation: serializeConversation(conversation),
  };
}

function stableConversationId(userId) {
  return `miniapp-${userId}-main`;
}

function stableSessionId(userId) {
  return `miniapp-session-${userId}`;
}

function createChatManager(options = {}) {
  const workspaceRoot = path.resolve(options.workspaceRoot || process.cwd());
  const executeTurn = options.executeTurn || defaultExecuteTurn;
  const conversations = new Map();
  const runs = new Map();
  const runQueue = new Map();

  function ensureConversation(user) {
    const userId = String(user && user.id ? user.id : "unknown");
    const conversationId = stableConversationId(userId);
    if (!conversations.has(conversationId)) {
      conversations.set(conversationId, {
        conversationId,
        sessionId: stableSessionId(userId),
        userId,
        updatedAt: now(),
        latestRunId: "",
        messages: [],
      });
    }
    return conversations.get(conversationId);
  }

  function getConversationById(conversationId) {
    return conversations.get(String(conversationId || "")) || null;
  }

  function pushEvent(run, type, extra = {}) {
    run.nextEventId += 1;
    const event = {
      id: run.nextEventId,
      type,
      ts: now(),
      ...extra,
    };
    run.events.push(event);
    const payload = JSON.stringify(serializeRun(run, getConversationById(run.conversationId)));
    for (const subscriber of run.subscribers) {
      subscriber.write(`id: ${event.id}\n`);
      subscriber.write(`event: run\n`);
      subscriber.write(`data: ${payload}\n\n`);
    }
  }

  async function executeQueuedRun(run) {
    const conversation = getConversationById(run.conversationId);
    if (!conversation) return;

    run.status = "running";
    pushEvent(run, "run.started", { status: run.status, message: "Routing into ORION." });

    const heartbeat = setInterval(() => {
      if (run.status !== "running") return;
      pushEvent(run, "run.status", { status: run.status, message: "ORION is thinking on the bridge..." });
    }, 2500);
    heartbeat.unref?.();

    try {
      const result = await executeTurn({
        workspaceRoot,
        sessionId: conversation.sessionId,
        message: run.prompt,
      });
      clearInterval(heartbeat);

      if (!result.ok) {
        run.status = "failed";
        run.error = userFacingRuntimeError(result.error);
        run.completedAt = now();
        pushEvent(run, "run.failed", { status: run.status, message: run.error });
        return;
      }

      const assistantMessage = {
        id: randomId("msg"),
        role: "assistant",
        text: result.text || "ORION completed the turn without a visible reply.",
        createdAt: now(),
      };
      conversation.messages.push(assistantMessage);
      conversation.updatedAt = now();
      run.lastMessage = assistantMessage.text;
      run.status = "completed";
      run.completedAt = now();
      pushEvent(run, "run.completed", {
        status: run.status,
        message: "ORION is back on the bridge.",
      });
    } catch (error) {
      clearInterval(heartbeat);
      run.status = "failed";
      run.error = userFacingRuntimeError(error instanceof Error ? error.message : String(error || ""));
      run.completedAt = now();
      pushEvent(run, "run.failed", { status: run.status, message: run.error });
    } finally {
      for (const subscriber of run.subscribers) {
        subscriber.end();
      }
      run.subscribers.clear();
    }
  }

  function scheduleRun(run) {
    const pending = runQueue.get(run.conversationId) || Promise.resolve();
    const next = pending.then(() => executeQueuedRun(run)).catch(() => executeQueuedRun(run));
    runQueue.set(run.conversationId, next.finally(() => {
      if (runQueue.get(run.conversationId) === next) {
        runQueue.delete(run.conversationId);
      }
    }));
  }

  function createRun(user, message) {
    const conversation = ensureConversation(user);
    const run = {
      runId: randomId("run"),
      conversationId: conversation.conversationId,
      createdAt: now(),
      completedAt: null,
      status: "queued",
      error: "",
      lastMessage: "",
      prompt: String(message || "").trim(),
      nextEventId: 0,
      events: [],
      subscribers: new Set(),
    };

    const userMessage = {
      id: randomId("msg"),
      role: "user",
      text: run.prompt,
      createdAt: now(),
    };
    conversation.messages.push(userMessage);
    conversation.updatedAt = now();
    conversation.latestRunId = run.runId;
    runs.set(run.runId, run);
    pushEvent(run, "run.queued", { status: run.status, message: "Queued on the ORION bridge." });
    scheduleRun(run);
    return serializeRun(run, conversation);
  }

  function bootstrap(user) {
    const conversation = ensureConversation(user);
    return serializeConversation(conversation);
  }

  function getRun(runId) {
    const run = runs.get(String(runId || ""));
    if (!run) return null;
    const conversation = getConversationById(run.conversationId);
    if (!conversation) return null;
    return serializeRun(run, conversation);
  }

  function subscribe(runId, res, lastEventId) {
    const run = runs.get(String(runId || ""));
    if (!run) return false;

    const lastSeen = Number.parseInt(String(lastEventId || "0"), 10) || 0;
    res.writeHead(200, {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    });
    res.write(": connected\n\n");

    const payload = serializeRun(run, getConversationById(run.conversationId));
    for (const event of run.events) {
      if (event.id <= lastSeen) continue;
      res.write(`id: ${event.id}\n`);
      res.write("event: run\n");
      res.write(`data: ${JSON.stringify(payload)}\n\n`);
    }

    if (run.status === "completed" || run.status === "failed") {
      res.end();
      return true;
    }

    const keepAlive = setInterval(() => {
      res.write(": keepalive\n\n");
    }, 15000);
    keepAlive.unref?.();
    run.subscribers.add(res);
    res.on("close", () => {
      clearInterval(keepAlive);
      run.subscribers.delete(res);
    });
    return true;
  }

  return {
    bootstrap,
    createRun,
    getRun,
    subscribe,
  };
}

function defaultExecuteTurn({ workspaceRoot, sessionId, message }) {
  return new Promise((resolve) => {
    const child = spawn(
      "python3",
      [
        "scripts/openclaw_guarded_turn.py",
        "--repo-root",
        workspaceRoot,
        "--agent",
        "main",
        "--runtime-channel",
        "local",
        "--session-id",
        sessionId,
        "--thinking",
        "medium",
        "--timeout",
        "180",
        "--message",
        message,
      ],
      {
        cwd: workspaceRoot,
        env: { ...process.env },
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", (error) => {
      resolve({ ok: false, error: error.message, text: "" });
    });
    child.on("close", (code) => {
      if (code === 0) {
        resolve({ ok: true, text: String(stdout || "").trim(), error: "" });
        return;
      }
      resolve({ ok: false, error: String(stderr || stdout || "").trim(), text: "" });
    });
  });
}

module.exports = {
  createChatManager,
  defaultExecuteTurn,
  stableConversationId,
  stableSessionId,
  userFacingRuntimeError,
};
