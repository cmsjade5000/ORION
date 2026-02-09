import type { Artifact } from "../api/state";

function ext(name: string) {
  const n = String(name || "").trim();
  const i = n.lastIndexOf(".");
  if (i <= 0 || i === n.length - 1) return "";
  return n.slice(i + 1).toLowerCase();
}

function isExternalUrl(url: string) {
  const u = String(url || "");
  if (!u) return false;
  if (u.startsWith("/api/artifacts/")) return false;
  return /^https?:\/\//i.test(u);
}

export function emojiForArtifact(a: Pick<Artifact, "mime" | "name" | "url">): string {
  const mime = String(a.mime || "").toLowerCase();
  const name = String(a.name || "");
  const e = ext(name);
  const external = isExternalUrl(String(a.url || ""));

  // PDFs
  if (mime === "application/pdf" || e === "pdf") return "📄";

  // Images
  if (mime.startsWith("image/") || ["png", "jpg", "jpeg", "webp", "gif", "avif", "heic"].includes(e)) return "🖼️";

  // Spreadsheets
  if (
    mime === "text/csv" ||
    mime === "application/vnd.ms-excel" ||
    mime === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    ["csv", "xls", "xlsx", "ods"].includes(e)
  ) {
    return "📊";
  }

  // Archives
  if (
    ["application/zip", "application/x-zip-compressed", "application/x-tar", "application/gzip", "application/x-7z-compressed"].includes(mime) ||
    ["zip", "tar", "gz", "tgz", "7z"].includes(e)
  ) {
    return "🗜️";
  }

  // Audio
  if (mime.startsWith("audio/") || ["mp3", "wav", "ogg", "m4a", "flac"].includes(e)) return "🎧";

  // Video
  if (mime.startsWith("video/") || ["mp4", "webm", "mov", "mkv"].includes(e)) return "🎬";

  // JSON
  if (mime === "application/json" || e === "json") return "🧩";

  // Text
  if (
    mime.startsWith("text/") ||
    ["txt", "md", "log"].includes(e)
  ) {
    return "📝";
  }

  // Links (when the artifact is primarily a URL)
  if (external) return "🔗";

  // Fallback
  return "📎";
}
