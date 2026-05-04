const MAX_PAYLOAD_BYTES = Math.max(
  1,
  Number.parseInt(process.env.ORION_MINIAPP_PAYLOAD_MAX_BYTES || "4096", 10)
);
const MAX_SUBPROCESS_TIMEOUT_MS = Math.max(
  1_000,
  Number.parseInt(process.env.ORION_MINIAPP_SUBPROCESS_TIMEOUT_MS || "15000", 10)
);
const MAX_SUBPROCESS_CONCURRENCY = Math.max(
  1,
  Number.parseInt(process.env.ORION_MINIAPP_SUBPROCESS_CONCURRENCY || "4", 10)
);
const MAX_JSON_BYTES = Math.max(1, Number.parseInt(process.env.ORION_MINIAPP_MAX_JSON_BYTES || "524288", 10));

let activeSubprocesses = 0;
const subprocessWaiters = [];

function waitForSlot() {
  return new Promise((resolve) => {
    subprocessWaiters.push(resolve);
  });
}

async function acquireSubprocessSlot() {
  if (activeSubprocesses < MAX_SUBPROCESS_CONCURRENCY) {
    activeSubprocesses += 1;
    return () => {
      activeSubprocesses -= 1;
      const next = subprocessWaiters.shift();
      if (next) {
        next();
      }
    };
  }

  await waitForSlot();
  return acquireSubprocessSlot();
}

function normalizeTextPayload(raw) {
  return String(raw || "").trim();
}

function assertPayloadLimit(raw, context = "payload") {
  const value = normalizeTextPayload(raw);
  if (Buffer.byteLength(value, "utf-8") > MAX_PAYLOAD_BYTES) {
    throw new Error(`${context} exceeds ${MAX_PAYLOAD_BYTES} bytes`);
  }
  return value;
}

async function withSubprocessSlot(fn) {
  const release = await acquireSubprocessSlot();
  try {
    return await fn();
  } finally {
    if (typeof release === "function") {
      release();
    }
  }
}

function safeJsonPayload(raw) {
  const rawText = normalizeTextPayload(raw);
  if (Buffer.byteLength(rawText, "utf-8") > MAX_JSON_BYTES) {
    throw new Error(`subprocess output exceeds safe JSON size (${MAX_JSON_BYTES} bytes)`);
  }
  return rawText;
}

module.exports = {
  MAX_JSON_BYTES,
  MAX_PAYLOAD_BYTES,
  MAX_SUBPROCESS_CONCURRENCY,
  MAX_SUBPROCESS_TIMEOUT_MS,
  assertPayloadLimit,
  acquireSubprocessSlot,
  withSubprocessSlot,
  safeJsonPayload,
};
