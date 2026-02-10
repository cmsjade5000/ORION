#!/usr/bin/env node
/* eslint-disable no-console */

const { listVoices, textToSpeechToFile } = require("./manifest");

function usage(code = 2) {
  console.error(
    [
      "Usage:",
      "  node skills/elevenlabs-tts/cli.js list-voices",
      "  node skills/elevenlabs-tts/cli.js speak --text <text> [--voice-id <id> | --voice-name <name>] [--preset calm|energetic|narration|urgent]",
      "  node skills/elevenlabs-tts/cli.js audio-check",
      "",
      "Notes:",
      "  - On success, speak/audio-check print only a single MEDIA:/abs/path.mp3 line to stdout.",
    ].join("\n"),
  );
  process.exit(code);
}

function getFlag(args, name) {
  const idx = args.indexOf(name);
  if (idx === -1) return null;
  const v = args[idx + 1];
  if (!v || v.startsWith("--")) return "";
  return v;
}

async function main() {
  const args = process.argv.slice(2);
  const cmd = args[0];
  if (!cmd || cmd === "-h" || cmd === "--help") usage(0);

  if (cmd === "list-voices") {
    const voices = await listVoices();
    for (const v of voices) {
      const id = String(v?.voice_id || "").trim();
      const name = String(v?.name || "").trim();
      if (!id) continue;
      console.log(`${id}\t${name}`);
    }
    return;
  }

  if (cmd === "speak") {
    const text = getFlag(args, "--text");
    const voiceId = getFlag(args, "--voice-id");
    const voiceName = getFlag(args, "--voice-name");
    const preset = getFlag(args, "--preset");

    if (!text) usage(2);

    // textToSpeechToFile prints MEDIA: on success.
    await textToSpeechToFile({
      text,
      voiceId: voiceId || undefined,
      voiceName: voiceName || undefined,
      voiceSettingsPreset: preset || undefined,
      filenamePrefix: "orion_tts",
    });
    return;
  }

  if (cmd === "audio-check") {
    const voices = await listVoices();
    const first = voices.find((v) => v?.voice_id);
    if (!first?.voice_id) {
      throw new Error("No voices available for this ElevenLabs account.");
    }

    // Prefer a common default voice name if present, otherwise fallback to first voice.
    const preferredNames = ["Rachel", "Bella", "Adam", "Antoni", "Sarah", "Laura"];
    const preferred = voices.find((v) =>
      preferredNames.some((n) => String(v?.name || "").trim().toLowerCase() === n.toLowerCase()),
    );
    const voiceId = String((preferred?.voice_id || first.voice_id));

    await textToSpeechToFile({
      text: "This is a test of ORION's audio output.",
      voiceId,
      voiceSettingsPreset: "narration",
      filenamePrefix: "audio_check",
    });
    return;
  }

  usage(2);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
