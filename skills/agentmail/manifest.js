const fs = require("fs");
const os = require("os");
const path = require("path");

const fetchFn = globalThis.fetch ?? require("node-fetch");

function readFirstExistingFile(paths) {
  for (const p of paths) {
    try {
      if (p && fs.existsSync(p)) return fs.readFileSync(p, "utf8");
    } catch {
      // ignore
    }
  }
  return null;
}

function getAgentMailApiKey() {
  const fromEnv = process.env.AGENTMAIL_API_KEY?.trim();
  if (fromEnv) return fromEnv;

  const fromFile = readFirstExistingFile([
    process.env.AGENTMAIL_API_KEY_FILE,
    path.join(os.homedir(), ".openclaw", "secrets", "agentmail.api_key"),
    path.join(os.homedir(), ".openclaw", "secrets", "agentmail.key"),
  ]);

  const key = fromFile?.trim();
  if (key) return key;

  throw new Error(
    "AgentMail API key missing. Set AGENTMAIL_API_KEY or create ~/.openclaw/secrets/agentmail.api_key",
  );
}

function getBaseUrl() {
  const base = (process.env.AGENTMAIL_API_BASE ?? "https://api.agentmail.to/v0").trim();
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

async function agentmailRequest(method, pathname, body) {
  const apiKey = getAgentMailApiKey();
  const url = `${getBaseUrl()}${pathname.startsWith("/") ? "" : "/"}${pathname}`;

  const headers = {
    Authorization: `Bearer ${apiKey}`,
    Accept: "application/json",
  };

  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const res = await fetchFn(url, init);
  const text = await res.text();

  if (!res.ok) {
    // Avoid dumping secrets; include only status + response body.
    throw new Error(`AgentMail API ${res.status} ${res.statusText}: ${text}`);
  }

  if (!text) return null;
  return JSON.parse(text);
}

async function listInboxes(params = {}) {
  const qs = new URLSearchParams();
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.pageToken) qs.set("page_token", String(params.pageToken));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return agentmailRequest("GET", `/inboxes${suffix}`);
}

async function createInbox({ displayName } = {}) {
  const body = {};
  if (displayName) body.display_name = displayName;
  return agentmailRequest("POST", `/inboxes`, Object.keys(body).length ? body : undefined);
}

async function listMessages(inboxId, params = {}) {
  if (!inboxId) throw new Error("listMessages requires inboxId");
  const qs = new URLSearchParams();
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.pageToken) qs.set("page_token", String(params.pageToken));
  if (params.before) qs.set("before", String(params.before));
  if (params.after) qs.set("after", String(params.after));
  if (params.ascending != null) qs.set("ascending", params.ascending ? "true" : "false");
  if (params.includeSpam != null) qs.set("include_spam", params.includeSpam ? "true" : "false");
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return agentmailRequest("GET", `/inboxes/${encodeURIComponent(inboxId)}/messages${suffix}`);
}

async function getMessage(inboxId, messageId) {
  if (!inboxId || !messageId) throw new Error("getMessage requires inboxId and messageId");
  return agentmailRequest(
    "GET",
    `/inboxes/${encodeURIComponent(inboxId)}/messages/${encodeURIComponent(messageId)}`,
  );
}

async function sendMessage(inboxId, request = {}) {
  if (!inboxId) throw new Error("sendMessage requires inboxId");
  return agentmailRequest(
    "POST",
    `/inboxes/${encodeURIComponent(inboxId)}/messages/send`,
    request,
  );
}

module.exports = {
  listInboxes,
  createInbox,
  listMessages,
  getMessage,
  sendMessage,
};

