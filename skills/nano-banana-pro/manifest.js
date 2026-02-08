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

function getGeminiApiKey() {
  const fromEnv = process.env.GEMINI_API_KEY?.trim();
  if (fromEnv) return fromEnv;

  const fromFile = readFirstExistingFile([
    process.env.GEMINI_API_KEY_FILE,
    path.join(os.homedir(), ".openclaw", "secrets", "gemini.api_key"),
    path.join(os.homedir(), ".openclaw", "secrets", "gemini.key"),
  ]);

  const key = fromFile?.trim();
  if (key) return key;

  throw new Error(
    "Gemini API key missing. Set GEMINI_API_KEY or create ~/.openclaw/secrets/gemini.api_key",
  );
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function safeSlug(s) {
  return String(s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

async function generateImage({
  prompt,
  model = "gemini-2.5-flash-image",
  aspectRatio,
  imageSize,
  filenamePrefix = "nano_banana",
  outDir = path.resolve("tmp", "nano-banana"),
} = {}) {
  if (!prompt || !String(prompt).trim()) throw new Error("generateImage requires prompt");

  const apiKey = getGeminiApiKey();
  ensureDir(outDir);

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;

  const body = {
    contents: [
      {
        role: "user",
        parts: [{ text: String(prompt) }],
      },
    ],
  };

  // The image models accept generation config fields; unused fields are ignored by some models.
  const generationConfig = {};
  if (aspectRatio) generationConfig.aspectRatio = aspectRatio;
  if (imageSize) generationConfig.imageSize = imageSize;
  if (Object.keys(generationConfig).length) body.generationConfig = generationConfig;

  const res = await fetchFn(url, {
    method: "POST",
    headers: {
      "x-goog-api-key": apiKey,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  });

  const json = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(
      `Gemini image API ${res.status} ${res.statusText}: ${json ? JSON.stringify(json) : "(no body)"}`,
    );
  }

  const parts =
    json?.candidates?.[0]?.content?.parts ??
    json?.candidates?.[0]?.content?.Parts ??
    [];

  const inline =
    parts.find((p) => p?.inlineData?.data)?.inlineData ??
    parts.find((p) => p?.inline_data?.data)?.inline_data ??
    null;

  if (!inline?.data) {
    throw new Error(`Gemini image API returned no inline image data. Response keys: ${Object.keys(json || {})}`);
  }

  const mimeType = inline.mimeType || inline.mime_type || "image/png";
  const ext = mimeType.includes("png") ? "png" : mimeType.includes("jpeg") || mimeType.includes("jpg") ? "jpg" : "bin";

  const fileName = `${safeSlug(filenamePrefix)}_${nowStamp()}.${ext}`;
  const outPath = path.join(outDir, fileName);

  fs.writeFileSync(outPath, Buffer.from(inline.data, "base64"));

  // OpenClaw attachment contract: MEDIA: line with a local path.
  const abs = path.resolve(outPath);
  const mediaLine = `MEDIA:${abs}`;
  console.log(mediaLine);
  return mediaLine;
}

module.exports = { generateImage };

