from __future__ import annotations

import json
import re

_INLINE_PATTERNS = [
    re.compile(r"OLCALL>.*?(?:CALL>|ALL>)", flags=re.IGNORECASE | re.DOTALL),
    re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL),
]

_FINAL_BLOCK_RE = re.compile(r"<final>\s*(.*?)\s*</final>", flags=re.IGNORECASE | re.DOTALL)

_LINE_MARKERS = (
    "OLCALL>",
    "CALL>",
    "ALL>",
    '"type":"toolCall"',
    '"type": "toolCall"',
    '"type":"toolResult"',
    '"type": "toolResult"',
    '"type":"thinking"',
    '"type": "thinking"',
)

_TAGGED_LINE_RE = re.compile(r"^\s*(assistant|user|system)\s*:\s*", flags=re.IGNORECASE)

_JSON_ARTIFACT_KEYS = {"toolCall", "toolResult", "thinking"}


def contains_internal_artifacts(text: str) -> bool:
    s = str(text or "")
    if not s.strip():
        return False
    if any(marker in s for marker in _LINE_MARKERS):
        return True
    if "<think>" in s.lower() or "<final>" in s.lower():
        return True
    return _json_has_internal_artifacts(s)


def sanitize_outbound_text(text: str, *, placeholder: str = "Internal runtime output was suppressed.") -> str:
    raw = str(text or "")
    if not raw.strip():
        return ""

    cleaned = _FINAL_BLOCK_RE.sub(lambda m: m.group(1).strip(), raw)
    for pattern in _INLINE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r"(?im)^\s*</?final>\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*</?think>\s*$", "", cleaned)

    kept_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            kept_lines.append("")
            continue
        if any(marker in line for marker in _LINE_MARKERS):
            continue
        if _TAGGED_LINE_RE.match(stripped) and contains_internal_artifacts(stripped):
            continue
        kept_lines.append(line)

    collapsed = "\n".join(kept_lines)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed).strip()

    if collapsed and not contains_internal_artifacts(collapsed):
        return collapsed

    if _json_has_internal_artifacts(raw) or contains_internal_artifacts(raw):
        return placeholder

    return collapsed


def _json_has_internal_artifacts(text: str) -> bool:
    candidate = str(text or "").strip()
    if not candidate:
        return False

    obj = _try_parse_json(candidate)
    if obj is None:
        first = candidate.find("{")
        last = candidate.rfind("}")
        if first >= 0 and last > first:
            obj = _try_parse_json(candidate[first : last + 1])
    if obj is None:
        first = candidate.find("[")
        last = candidate.rfind("]")
        if first >= 0 and last > first:
            obj = _try_parse_json(candidate[first : last + 1])
    if obj is None:
        return False
    return _contains_artifact_obj(obj)


def _try_parse_json(candidate: str):
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _contains_artifact_obj(obj) -> bool:
    if isinstance(obj, dict):
        type_name = obj.get("type")
        if isinstance(type_name, str) and type_name in _JSON_ARTIFACT_KEYS:
            return True
        return any(_contains_artifact_obj(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_artifact_obj(v) for v in obj)
    return False
