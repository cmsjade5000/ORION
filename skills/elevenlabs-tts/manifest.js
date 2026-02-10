const fs = require("fs");
const os = require("os");
const path = require("path");

const fetchFn = globalThis.fetch ?? require("node-fetch");

let _openclawEnvVarsCache = null;
function getOpenClawEnvVars() {
  // Non-secret defaults can live in ~/.openclaw/openclaw.json under env.vars.
  // This allows the LaunchAgent gateway to provide stable defaults, and also
  // makes local CLI usage consistent with ORION's runtime.
  if (_openclawEnvVarsCache) return _openclawEnvVarsCache;

  const cfg =
    process.env.OPENCLAW_CONFIG_PATH?.trim() ||
    path.join(os.homedir(), ".openclaw", "openclaw.json");

  try {
    if (!fs.existsSync(cfg)) {
      _openclawEnvVarsCache = {};
      return _openclawEnvVarsCache;
    }
    const raw = fs.readFileSync(cfg, "utf8");
    const json = JSON.parse(raw);
    const vars = json?.env?.vars;
    _openclawEnvVarsCache = (vars && typeof vars === "object") ? vars : {};
    return _openclawEnvVarsCache;
  } catch {
    _openclawEnvVarsCache = {};
    return _openclawEnvVarsCache;
  }
}

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

function getElevenLabsApiKey() {
  const fromEnv = process.env.ELEVENLABS_API_KEY?.trim();
  if (fromEnv) return fromEnv;

  const fromFile = readFirstExistingFile([
    process.env.ELEVENLABS_API_KEY_FILE,
    path.join(os.homedir(), ".openclaw", "secrets", "elevenlabs.api_key"),
    path.join(os.homedir(), ".openclaw", "secrets", "elevenlabs.key"),
  ]);

  const key = fromFile?.trim();
  if (key) return key;

  throw new Error(
    "ElevenLabs API key missing. Set ELEVENLABS_API_KEY or create ~/.openclaw/secrets/elevenlabs.api_key",
  );
}

function getBaseUrl() {
  const base = (process.env.ELEVENLABS_API_BASE ?? "https://api.elevenlabs.io").trim();
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function safeSlug(s) {
  return String(s)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function nowStamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function parseKvList(s) {
  // Accept "k=v k2=v2" or "k:v;k2:v2" etc.
  const out = {};
  const raw = String(s || "").trim();
  if (!raw) return out;

  const parts = raw
    .split(/[;]+/g)
    .flatMap((p) => p.split(/\s+/g))
    .map((p) => p.trim())
    .filter(Boolean);

  for (const p of parts) {
    const m = p.match(/^([a-zA-Z_][a-zA-Z0-9_-]*)\s*[:=]\s*(.+)$/);
    if (!m) continue;
    const k = String(m[1] || "").trim().toLowerCase();
    const v = String(m[2] || "").trim();
    if (!k || !v) continue;
    out[k] = v;
  }
  return out;
}

function normalizePresetName(preset) {
  const p = String(preset || "").trim().toLowerCase();
  if (!p) return "";
  // Aliases so Cory can use casual tags while we keep only 4 real presets.
  const alias = {
    normal: "", // defer to configured defaults
    default: "", // defer to configured defaults
    warm: "calm",
    supportive: "calm",
    soothe: "calm",
    narrative: "narration",
    story: "narration",
    focus: "narration",
    brief: "narration",
    update: "narration",
    hype: "energetic",
    excited: "energetic",
    alert: "urgent",
    critical: "urgent",
  };
  return alias[p] || p;
}

function parseDirectiveLine(line) {
  // Returns { isDirective, preset, voiceId, voiceName }
  const first = String(line || "").trim();
  if (!first) return { isDirective: false, preset: "", voiceId: "", voiceName: "" };

  // Shorthand preset (and aliases).
  const presetShorthand = first.match(
    /^(?:#|\[)\s*(calm|narration|energetic|urgent|normal|default|warm|supportive|soothe|narrative|story|focus|brief|update|hype|excited|alert|critical)\s*(?:\]|$)/i,
  );
  if (presetShorthand && presetShorthand[1]) {
    return { isDirective: true, preset: normalizePresetName(presetShorthand[1]), voiceId: "", voiceName: "" };
  }

  // Key/value forms.
  const bracket = first.match(/^\[(?:tts|orion)\s+([^\]]+)\]$/i);
  const hash = first.match(/^#(?:tts|orion)\s*:?\s*(.+)$/i);
  const kv = bracket ? parseKvList(bracket[1]) : hash ? parseKvList(hash[1]) : null;
  if (!kv) return { isDirective: false, preset: "", voiceId: "", voiceName: "" };

  const preset = normalizePresetName(String(kv.preset || kv.style || "").trim());
  const voiceId = String(kv.voice_id || kv.voiceid || "").trim();
  const voiceName = String(kv.voice || kv.voice_name || kv.voicename || "").trim();
  return { isDirective: true, preset, voiceId, voiceName };
}

function extractInlineDirectives(text) {
  // Optional directives in the first non-empty line.
  //
  // Supported forms (first line only):
  // - "[urgent]" / "#urgent" (shorthand preset)
  // - "[tts preset=urgent]" / "[orion preset=calm voice_id=...]" (key/value)
  // - "#tts preset=urgent" / "#tts: preset=urgent"
  //
  // Returns: { text, preset, voiceId, voiceName }
  const raw = String(text ?? "");
  const lines = raw.split(/\r?\n/);
  const idx = lines.findIndex((ln) => String(ln).trim().length > 0);
  if (idx === -1) return { text: raw, preset: "", voiceId: "", voiceName: "" };

  const first = String(lines[idx]).trim();
  const parsed = parseDirectiveLine(first);
  if (!parsed.isDirective) return { text: raw, preset: "", voiceId: "", voiceName: "" };

  lines.splice(idx, 1);
  return { text: lines.join("\n"), preset: parsed.preset, voiceId: parsed.voiceId, voiceName: parsed.voiceName };
}

function splitTextByDirectives(text) {
  // Support multiple directive lines throughout the script to create multi-style segments.
  // Returns [{ preset, voiceId, voiceName, text }]
  const raw = String(text ?? "");
  const lines = raw.split(/\r?\n/);

  const segments = [];
  let curPreset = "";
  let curVoiceId = "";
  let curVoiceName = "";
  let curLines = [];

  function flush() {
    const body = curLines.join("\n").trim();
    if (!body) return;
    segments.push({
      preset: curPreset,
      voiceId: curVoiceId,
      voiceName: curVoiceName,
      text: body,
    });
    curLines = [];
  }

  for (const ln of lines) {
    const parsed = parseDirectiveLine(ln);
    if (parsed.isDirective) {
      const same =
        parsed.preset === curPreset &&
        parsed.voiceId === curVoiceId &&
        parsed.voiceName === curVoiceName;
      if (same) continue;

      if (curLines.join("").trim().length) flush();
      curPreset = parsed.preset;
      curVoiceId = parsed.voiceId;
      curVoiceName = parsed.voiceName;
      continue;
    }
    curLines.push(ln);
  }
  flush();

  return segments;
}

function acceptForOutputFormat(outputFormat) {
  const f = String(outputFormat || "").toLowerCase();
  if (f.startsWith("wav")) return "audio/wav";
  if (f.startsWith("mp3")) return "audio/mpeg";
  if (f.startsWith("pcm")) return "application/octet-stream";
  return "application/octet-stream";
}

function extForOutputFormat(outputFormat) {
  const f = String(outputFormat || "").toLowerCase();
  const head = f.split("_")[0] || "";
  if (head === "mp3") return "mp3";
  if (head === "wav") return "wav";
  if (head === "pcm") return "pcm";
  return "bin";
}

async function readResponseBodyForError(res) {
  // Best-effort without assuming JSON; keep it short.
  try {
    const text = await res.text();
    return text.length > 4000 ? `${text.slice(0, 4000)}…(truncated)` : text;
  } catch {
    return "(no body)";
  }
}

async function readResponseBytes(res) {
  if (typeof res.arrayBuffer === "function") {
    const ab = await res.arrayBuffer();
    return Buffer.from(ab);
  }
  // node-fetch v2
  if (typeof res.buffer === "function") return res.buffer();
  const text = await res.text();
  return Buffer.from(text, "binary");
}

async function elevenlabsRequest(method, pathname, opts = {}) {
  const apiKey = getElevenLabsApiKey();
  const base = getBaseUrl();
  const url = new URL(`${base}${pathname.startsWith("/") ? "" : "/"}${pathname}`);

  const qs = opts.query || {};
  for (const [k, v] of Object.entries(qs)) {
    if (v === undefined || v === null || v === "") continue;
    url.searchParams.set(k, String(v));
  }

  const headers = {
    "xi-api-key": apiKey,
    ...((opts.headers || {}) && opts.headers),
  };

  const init = { method, headers };
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.json);
  } else if (opts.body !== undefined) {
    init.body = opts.body;
  }

  const res = await fetchFn(url.toString(), init);
  if (!res.ok) {
    const body = await readResponseBodyForError(res);
    throw new Error(`ElevenLabs API ${res.status} ${res.statusText}: ${body}`);
  }
  return res;
}

async function listVoices() {
  const res = await elevenlabsRequest("GET", "/v1/voices", {
    headers: { Accept: "application/json" },
  });
  const text = await res.text();
  if (!text) return [];
  const json = JSON.parse(text);
  return Array.isArray(json?.voices) ? json.voices : [];
}

async function findVoiceIdByName(voiceName) {
  const want = String(voiceName || "").trim();
  if (!want) return null;

  const voices = await listVoices();
  const lower = want.toLowerCase();

  const exact = voices.find((v) => String(v?.name || "").trim().toLowerCase() === lower);
  if (exact?.voice_id) return String(exact.voice_id);

  const partial = voices.find((v) => String(v?.name || "").toLowerCase().includes(lower));
  if (partial?.voice_id) return String(partial.voice_id);

  return null;
}

async function getDefaultVoiceSettings() {
  const res = await elevenlabsRequest("GET", "/v1/voices/settings/default", {
    headers: { Accept: "application/json" },
  });
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

function presetVoiceSettings(preset) {
  const p = normalizePresetName(preset);
  if (!p) return null;
  if (p === "calm") return { stability: 0.65, similarity_boost: 0.75, style: 0.15, use_speaker_boost: true };
  if (p === "energetic") return { stability: 0.35, similarity_boost: 0.8, style: 0.6, use_speaker_boost: true };
  if (p === "narration") return { stability: 0.55, similarity_boost: 0.8, style: 0.3, use_speaker_boost: true };
  if (p === "urgent") return { stability: 0.28, similarity_boost: 0.85, style: 0.5, use_speaker_boost: true };
  return null;
}

function resolvePresetName(preset) {
  const direct = String(preset || "").trim();
  if (direct) return direct;

  const envPreset =
    process.env.ELEVENLABS_DEFAULT_PRESET?.trim() ||
    process.env.ELEVENLABS_PRESET?.trim() ||
    "";
  if (envPreset) return envPreset;

  const oc = getOpenClawEnvVars();
  const ocPreset = String(oc?.ELEVENLABS_DEFAULT_PRESET || oc?.ELEVENLABS_PRESET || "").trim();
  return ocPreset || "";
}

async function resolveVoiceId({ voiceId, voiceName } = {}) {
  let vid = String(voiceId || "").trim();
  if (vid) return vid;

  const name = String(voiceName || "").trim();
  if (name) {
    vid = await findVoiceIdByName(name);
    if (!vid) throw new Error(`No ElevenLabs voice matched name: ${name}`);
    return vid;
  }

  // Deterministic operator override (recommended for stable behavior).
  const envVoiceId =
    process.env.ELEVENLABS_DEFAULT_VOICE_ID?.trim() ||
    process.env.ELEVENLABS_VOICE_ID?.trim() ||
    "";
  if (envVoiceId) return envVoiceId;

  const envVoiceName =
    process.env.ELEVENLABS_DEFAULT_VOICE_NAME?.trim() ||
    process.env.ELEVENLABS_VOICE_NAME?.trim() ||
    "";
  if (envVoiceName) {
    vid = await findVoiceIdByName(envVoiceName);
    if (!vid) throw new Error(`No ElevenLabs voice matched name from env: ${envVoiceName}`);
    return vid;
  }

  // Next: OpenClaw config env.vars (stable across LaunchAgent runs).
  const oc = getOpenClawEnvVars();
  const ocVoiceId = String(oc?.ELEVENLABS_DEFAULT_VOICE_ID || oc?.ELEVENLABS_VOICE_ID || "").trim();
  if (ocVoiceId) return ocVoiceId;

  const ocVoiceName = String(oc?.ELEVENLABS_DEFAULT_VOICE_NAME || oc?.ELEVENLABS_VOICE_NAME || "").trim();
  if (ocVoiceName) {
    vid = await findVoiceIdByName(ocVoiceName);
    if (!vid) throw new Error(`No ElevenLabs voice matched name from OpenClaw config: ${ocVoiceName}`);
    return vid;
  }

  // Last resort: first available voice on the account.
  const voices = await listVoices();
  const first = voices.find((v) => v?.voice_id);
  if (first?.voice_id) return String(first.voice_id);

  throw new Error("No ElevenLabs voices available for this account.");
}

async function textToSpeechToFile({
  text,
  voiceId,
  voiceName,
  modelId = "eleven_multilingual_v2",
  outputFormat = "mp3_44100_128",
  optimizeStreamingLatency,
  voiceSettings,
  voiceSettingsPreset,
  filenamePrefix = "orion_tts",
  outDir = path.resolve("tmp", "elevenlabs-tts"),
  emitMediaLine = true,
} = {}) {
  const extracted = extractInlineDirectives(text);
  const t = String(extracted.text || "").trim();
  if (!t) throw new Error("textToSpeechToFile requires non-empty text");

  const vid = await resolveVoiceId({
    voiceId: voiceId || extracted.voiceId || undefined,
    voiceName: voiceName || extracted.voiceName || undefined,
  });

  const presetName = resolvePresetName(voiceSettingsPreset || extracted.preset || undefined);
  const preset = presetVoiceSettings(presetName);
  const vs = voiceSettings && typeof voiceSettings === "object" ? voiceSettings : preset;

  if (process.env.ELEVENLABS_TTS_DEBUG === "1") {
    // Stderr only, so stdout stays a single MEDIA: line for OpenClaw attachments.
    console.error(`[elevenlabs-tts] voiceId=${vid} preset=${presetName || "(none)"}`);
  }

  ensureDir(outDir);

  const body = {
    text: t,
    model_id: modelId,
  };
  if (vs) body.voice_settings = vs;

  const res = await elevenlabsRequest("POST", `/v1/text-to-speech/${encodeURIComponent(vid)}`, {
    query: {
      output_format: outputFormat,
      optimize_streaming_latency: optimizeStreamingLatency,
    },
    headers: {
      Accept: acceptForOutputFormat(outputFormat),
    },
    json: body,
  });

  const bytes = await readResponseBytes(res);
  const ext = extForOutputFormat(outputFormat);
  const fileName = `${safeSlug(filenamePrefix)}_${nowStamp()}.${ext}`;
  const outPath = path.join(outDir, fileName);
  fs.writeFileSync(outPath, bytes);

  const abs = path.resolve(outPath);
  const mediaLine = `MEDIA:${abs}`;
  // OpenClaw attachment contract: MEDIA: line with a local path.
  if (emitMediaLine) console.log(mediaLine);
  return { mediaLine, path: abs, voiceId: vid };
}

async function textToSpeechToFileMulti({
  text,
  voiceId,
  voiceName,
  modelId = "eleven_multilingual_v2",
  outputFormat = "mp3_44100_128",
  optimizeStreamingLatency,
  voiceSettings,
  voiceSettingsPreset,
  filenamePrefix = "orion_tts",
  outDir = path.resolve("tmp", "elevenlabs-tts"),
  emitMediaLine = true,
  // If ffmpeg is present, we prefer it. If not, we fall back to naive MP3 concat.
  preferFfmpeg = true,
} = {}) {
  const { spawnSync } = require("child_process");

  const segments = splitTextByDirectives(text);
  if (!segments.length) throw new Error("textToSpeechToFileMulti requires non-empty text");

  // Single segment: behave like normal, but preserve segment metadata.
  if (segments.length === 1) {
    const seg = segments[0];
    const preset = seg.preset || voiceSettingsPreset || "";
    return textToSpeechToFile({
      text: seg.text,
      voiceId: voiceId || seg.voiceId || undefined,
      voiceName: voiceName || seg.voiceName || undefined,
      modelId,
      outputFormat,
      optimizeStreamingLatency,
      voiceSettings,
      voiceSettingsPreset: preset ? preset : undefined,
      filenamePrefix,
      outDir,
      emitMediaLine,
    });
  }

  ensureDir(outDir);

  const segPaths = [];
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    const preset = seg.preset || voiceSettingsPreset || "";
    const r = await textToSpeechToFile({
      text: seg.text,
      voiceId: voiceId || seg.voiceId || undefined,
      voiceName: voiceName || seg.voiceName || undefined,
      modelId,
      outputFormat,
      optimizeStreamingLatency,
      voiceSettings,
      voiceSettingsPreset: preset ? preset : undefined,
      filenamePrefix: `${filenamePrefix}_seg${i + 1}`,
      outDir,
      emitMediaLine: false,
    });
    segPaths.push(r.path);
  }

  const ext = extForOutputFormat(outputFormat);
  const outPath = path.join(outDir, `${safeSlug(filenamePrefix)}_${nowStamp()}.${ext}`);
  const absOut = path.resolve(outPath);

  const haveFfmpeg =
    preferFfmpeg &&
    (() => {
      try {
        const r = spawnSync("ffmpeg", ["-version"], { stdio: "ignore" });
        return r && r.status === 0;
      } catch {
        return false;
      }
    })();

  if (haveFfmpeg) {
    const listPath = path.join(outDir, `${safeSlug(filenamePrefix)}_${nowStamp()}_concat.txt`);
    const listBody = segPaths.map((p) => `file '${String(p).replace(/'/g, "'\\''")}'`).join("\n") + "\n";
    fs.writeFileSync(listPath, listBody, "utf8");

    const r = spawnSync(
      "ffmpeg",
      [
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        listPath,
        // Re-encode to avoid timestamp/dts issues that can happen with MP3 stream copy.
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        absOut,
      ],
      { stdio: "inherit" },
    );
    if (!r || r.status !== 0) {
      // Fall back if ffmpeg concat failed for any reason (codec mismatch, etc).
      fs.unlinkSync(listPath);
    } else {
      fs.unlinkSync(listPath);
    }
  }

  // If ffmpeg didn't produce the file, fall back to naive MP3 concat.
  if (!fs.existsSync(absOut) || fs.statSync(absOut).size === 0) {
    const out = fs.createWriteStream(absOut);
    for (const p of segPaths) {
      out.write(fs.readFileSync(p));
    }
    out.end();
    await new Promise((resolve) => out.on("close", resolve));
  }

  const mediaLine = `MEDIA:${absOut}`;
  if (emitMediaLine) console.log(mediaLine);
  return { mediaLine, path: absOut };
}

module.exports = {
  listVoices,
  findVoiceIdByName,
  getDefaultVoiceSettings,
  resolveVoiceId,
  resolvePresetName,
  splitTextByDirectives,
  extractInlineDirectives,
  textToSpeechToFile,
  textToSpeechToFileMulti,
};
