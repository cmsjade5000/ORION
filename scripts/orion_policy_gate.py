#!/usr/bin/env python3
"""
Runtime policy gate for ORION outputs.

Contract:
- exit 0 when policy passes OR only audit-mode violations exist
- exit 2 when at least one block-mode violation exists
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


VALID_MODES = {"audit", "block"}


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    description: str
    severity: str
    mode: str
    validator: str
    applies_to: tuple[str, ...]
    trigger_tags_any: tuple[str, ...]
    trigger_tags_all: tuple[str, ...]
    trigger_request_any: tuple[str, ...]
    trigger_response_any: tuple[str, ...]
    required_any: tuple[str, ...]
    required_all: tuple[str, ...]
    forbidden_any: tuple[str, ...]
    exact_any: tuple[str, ...]
    exact_response: str
    claim_any: tuple[str, ...]
    allowed_progress_any: tuple[str, ...]
    evidence_any: tuple[str, ...]
    remediation: str


@dataclasses.dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: str
    configured_mode: str
    effective_mode: str
    description: str
    remediation: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "configured_mode": self.configured_mode,
            "effective_mode": self.effective_mode,
            "description": self.description,
            "remediation": self.remediation,
            "reason": self.reason,
            "blocking": self.effective_mode == "block",
        }


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _to_lower_set(values: list[str] | tuple[str, ...] | None) -> set[str]:
    if not values:
        return set()
    out: set[str] = set()
    for value in values:
        s = str(value).strip().lower()
        if s:
            out.add(s)
    return out


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    if not needles:
        return False
    t = text.lower()
    return any(n.lower() in t for n in needles if n)


def _missing_required_all(text: str, required_all: tuple[str, ...]) -> list[str]:
    t = text.lower()
    missing: list[str] = []
    for needle in required_all:
        if needle and needle.lower() not in t:
            missing.append(needle)
    return missing


def infer_tags(*, request_text: str, response_text: str, initial_tags: set[str] | None = None) -> set[str]:
    tags = set(initial_tags or set())
    req = request_text.lower()
    resp = response_text.lower()

    if any(k in req for k in ("cron", "schedule", "every weekday", "reminder", "run every")):
        tags.update({"cron", "scheduling", "reminder", "operational_change"})

    if any(k in req for k in ("set up", "configure", "restart", "deploy", "open port", "enable", "disable", "service")):
        tags.add("operational_change")
        tags.add("ops")

    if any(k in req for k in ("i don't want to be here", "not safe", "suicide", "kill myself", "hurt myself", "self-harm")):
        tags.add("crisis")

    if any(k in req for k in ("wipe", "reset everything", "delete all", "destroy", "format", "rm -rf", "erase")):
        tags.add("destructive")

    explore = any(k in req for k in ("explore", "brainstorm", "research", "options", "what's possible"))
    execute = any(k in req for k in ("execute", "implement", "ship", "do it", "set it up", "run it now"))
    if explore and execute:
        tags.add("mixed_intent")

    if ("subagent task" in req and "just completed" in req) or ("announce results" in req):
        tags.add("announce_prompt")

    # If the response itself clearly indicates one of the states, preserve useful context.
    if any(k in resp for k in ("queued", "in progress", "pending verification")):
        tags.add("progress_state")

    return tags


def _parse_rule(raw: dict[str, Any], *, default_mode: str) -> Rule:
    mode = str(raw.get("mode") or default_mode).strip().lower()
    if mode not in VALID_MODES:
        mode = default_mode

    return Rule(
        id=str(raw.get("id") or "").strip(),
        description=str(raw.get("description") or "").strip(),
        severity=str(raw.get("severity") or "medium").strip().lower(),
        mode=mode,
        validator=str(raw.get("validator") or "phrase_contract").strip(),
        applies_to=tuple(str(x).strip().lower() for x in (raw.get("applies_to") or []) if str(x).strip()),
        trigger_tags_any=tuple(str(x).strip().lower() for x in (raw.get("trigger_tags_any") or []) if str(x).strip()),
        trigger_tags_all=tuple(str(x).strip().lower() for x in (raw.get("trigger_tags_all") or []) if str(x).strip()),
        trigger_request_any=tuple(str(x) for x in (raw.get("trigger_request_any") or []) if str(x).strip()),
        trigger_response_any=tuple(str(x) for x in (raw.get("trigger_response_any") or []) if str(x).strip()),
        required_any=tuple(str(x) for x in (raw.get("required_any") or []) if str(x).strip()),
        required_all=tuple(str(x) for x in (raw.get("required_all") or []) if str(x).strip()),
        forbidden_any=tuple(str(x) for x in (raw.get("forbidden_any") or []) if str(x).strip()),
        exact_any=tuple(str(x) for x in (raw.get("exact_any") or []) if str(x).strip()),
        exact_response=str(raw.get("exact_response") or "").strip(),
        claim_any=tuple(str(x) for x in (raw.get("claim_any") or []) if str(x).strip()),
        allowed_progress_any=tuple(str(x) for x in (raw.get("allowed_progress_any") or []) if str(x).strip()),
        evidence_any=tuple(str(x) for x in (raw.get("evidence_any") or []) if str(x).strip()),
        remediation=str(raw.get("remediation") or "").strip(),
    )


def load_rule_set(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    default_mode = str(doc.get("default_mode") or "audit").strip().lower()
    if default_mode not in VALID_MODES:
        default_mode = "audit"

    rules = [_parse_rule(raw, default_mode=default_mode) for raw in (doc.get("rules") or [])]
    return {
        "path": str(path),
        "version": int(doc.get("version") or 1),
        "name": str(doc.get("name") or "orion_runtime_policy"),
        "default_mode": default_mode,
        "rules": rules,
    }


def _rule_applies(rule: Rule, *, scope: str, request_text: str, response_text: str, tags: set[str]) -> bool:
    if rule.applies_to and scope not in rule.applies_to:
        return False

    if rule.trigger_tags_any and not (tags & set(rule.trigger_tags_any)):
        return False

    if rule.trigger_tags_all and not set(rule.trigger_tags_all).issubset(tags):
        return False

    if rule.trigger_request_any and not _contains_any(request_text, rule.trigger_request_any):
        return False

    if rule.trigger_response_any and not _contains_any(response_text, rule.trigger_response_any):
        return False

    # If no trigger clauses are present, it applies by default in-scope.
    return True


def _effective_mode(*, configured_mode: str, run_mode: str) -> str:
    if run_mode == "audit":
        return "audit"
    return configured_mode if configured_mode in VALID_MODES else "block"


def _eval_phrase_contract(rule: Rule, *, response_text: str) -> str | None:
    if rule.required_any and not _contains_any(response_text, rule.required_any):
        return f"missing required_any phrases: {list(rule.required_any)}"

    missing = _missing_required_all(response_text, rule.required_all)
    if missing:
        return f"missing required_all phrases: {missing}"

    if rule.forbidden_any and _contains_any(response_text, rule.forbidden_any):
        return f"contains forbidden phrase from: {list(rule.forbidden_any)}"

    if rule.exact_any and not any(ex in response_text for ex in rule.exact_any):
        return f"missing exact phrase from: {list(rule.exact_any)}"

    return None


def _eval_announce_skip_exact(rule: Rule, *, response_text: str) -> str | None:
    expected = rule.exact_response or "ANNOUNCE_SKIP"
    if response_text.strip() != expected:
        return f"announce response must be exactly '{expected}'"
    return None


def _eval_operational_claim_requires_evidence(
    rule: Rule,
    *,
    response_text: str,
    metadata: dict[str, Any],
) -> str | None:
    if bool(metadata.get("executed_in_turn")) or bool(metadata.get("has_specialist_result")):
        return None

    if rule.allowed_progress_any and _contains_any(response_text, rule.allowed_progress_any):
        return None

    claim_any = rule.claim_any or ("done", "completed", "configured", "set up")
    if not _contains_any(response_text, claim_any):
        return None

    evidence_any = rule.evidence_any or ("proof:", "verification", "result:")
    if _contains_any(response_text, evidence_any):
        return None

    return "claims completion without explicit verification evidence or specialist Result"


def evaluate_policy(
    *,
    payload: dict[str, Any],
    rule_set: dict[str, Any],
    run_mode: str,
) -> dict[str, Any]:
    mode = str(run_mode).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"invalid run mode: {run_mode}")

    scope = str(payload.get("scope") or "orion_reply").strip().lower()
    request_text = str(payload.get("request_text") or "")
    response_text = str(payload.get("response_text") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    tags = _to_lower_set(payload.get("tags") if isinstance(payload.get("tags"), list) else [])
    tags = infer_tags(request_text=request_text, response_text=response_text, initial_tags=tags)

    violations: list[Violation] = []
    evaluated = 0

    for rule in rule_set["rules"]:
        if not rule.id:
            continue
        if not _rule_applies(rule, scope=scope, request_text=request_text, response_text=response_text, tags=tags):
            continue

        evaluated += 1
        if rule.validator == "phrase_contract":
            reason = _eval_phrase_contract(rule, response_text=response_text)
        elif rule.validator == "announce_skip_exact":
            reason = _eval_announce_skip_exact(rule, response_text=response_text)
        elif rule.validator == "operational_claim_requires_evidence":
            reason = _eval_operational_claim_requires_evidence(rule, response_text=response_text, metadata=metadata)
        else:
            reason = f"unknown validator: {rule.validator}"

        if reason:
            eff_mode = _effective_mode(configured_mode=rule.mode, run_mode=mode)
            violations.append(
                Violation(
                    rule_id=rule.id,
                    severity=rule.severity,
                    configured_mode=rule.mode,
                    effective_mode=eff_mode,
                    description=rule.description,
                    remediation=rule.remediation,
                    reason=reason,
                )
            )

    blocking = [v for v in violations if v.effective_mode == "block"]

    report = {
        "kind": "orion_policy_gate",
        "timestamp": _now_iso(),
        "rules": {
            "path": rule_set["path"],
            "name": rule_set["name"],
            "version": rule_set["version"],
            "default_mode": rule_set["default_mode"],
        },
        "mode": mode,
        "input": {
            "scope": scope,
            "request_text": request_text,
            "response_text": response_text,
            "tags": sorted(tags),
            "metadata": metadata,
        },
        "summary": {
            "total_rules": len(rule_set["rules"]),
            "evaluated_rules": evaluated,
            "violations": len(violations),
            "blocking_violations": len(blocking),
            "passed": len(violations) == 0,
            "blocked": len(blocking) > 0,
        },
        "violations": [v.as_dict() for v in violations],
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines: list[str] = []
    lines.append("# ORION Policy Gate Report")
    lines.append("")
    lines.append(f"- Timestamp: `{report.get('timestamp', '')}`")
    lines.append(f"- Mode: `{report.get('mode', '')}`")
    lines.append(f"- Scope: `{((report.get('input') or {}).get('scope', ''))}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Evaluated rules: `{summary.get('evaluated_rules', 0)}` / `{summary.get('total_rules', 0)}`")
    lines.append(f"- Violations: `{summary.get('violations', 0)}`")
    lines.append(f"- Blocking violations: `{summary.get('blocking_violations', 0)}`")
    lines.append(f"- Blocked: `{summary.get('blocked', False)}`")
    lines.append("")

    violations = report.get("violations", [])
    if not violations:
        lines.append("No violations.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Violations")
    lines.append("")
    for idx, item in enumerate(violations, start=1):
        lines.append(f"{idx}. `{item.get('rule_id')}` ({item.get('effective_mode')}, {item.get('severity')})")
        lines.append(f"   - Reason: {item.get('reason', '')}")
        remediation = str(item.get("remediation") or "").strip()
        if remediation:
            lines.append(f"   - Remediation: {remediation}")
    lines.append("")
    return "\n".join(lines)


def _default_rules_path() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "config" / "orion_policy_rules.json"


def _load_input(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Run ORION runtime policy checks.")
    ap.add_argument("--input-json", required=True, help="Input payload JSON path")
    ap.add_argument("--rules", default=str(_default_rules_path()), help="Rule manifest JSON path")
    ap.add_argument("--mode", choices=["audit", "block"], default="audit", help="Runtime policy mode")
    ap.add_argument("--output-json", default="", help="Write structured report JSON to this path")
    ap.add_argument("--output-md", default="", help="Write markdown summary to this path")
    args = ap.parse_args()

    input_path = Path(args.input_json).resolve()
    rules_path = Path(args.rules).resolve()
    payload = _load_input(input_path)
    rule_set = load_rule_set(rules_path)
    report = evaluate_policy(payload=payload, rule_set=rule_set, run_mode=args.mode)

    if args.output_json:
        out_json = Path(args.output_json).resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = render_markdown(report)
    if args.output_md:
        out_md = Path(args.output_md).resolve()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md, encoding="utf-8")

    print("POLICY_GATE")
    print(f"input: {input_path}")
    print(f"rules: {rules_path}")
    print(f"mode: {args.mode}")
    print(f"evaluated_rules: {report['summary']['evaluated_rules']}")
    print(f"violations: {report['summary']['violations']}")
    print(f"blocking_violations: {report['summary']['blocking_violations']}")

    return 2 if report["summary"]["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
