#!/usr/bin/env python3
"""
Compare routing-sim eval reports and enforce regression gates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_report(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics(report: dict) -> dict:
    summary = report.get("summary", {})
    passed = int(summary.get("pass", 0))
    failed = int(summary.get("fail", 0))
    total = max(0, passed + failed)
    results = report.get("results", [])
    avg_total = round(sum(int(r.get("total", 0)) for r in results) / len(results), 2) if results else 0.0
    return {
        "confidence": int(report.get("confidence", 0)),
        "pass": passed,
        "fail": failed,
        "total": total,
        "pass_rate": round((passed / total), 4) if total else 0.0,
        "safety_zeros": int(summary.get("safety_zeros", 0)),
        "avg_prompt_score": avg_total,
    }


def _prompt_deltas(baseline: dict, current: dict) -> list[dict]:
    by_num_base = {int(r.get("num", -1)): r for r in baseline.get("results", [])}
    out: list[dict] = []
    for r in current.get("results", []):
        num = int(r.get("num", -1))
        b = by_num_base.get(num)
        if b is None:
            continue
        out.append(
            {
                "num": num,
                "title": r.get("title", ""),
                "baseline_total": int(b.get("total", 0)),
                "current_total": int(r.get("total", 0)),
                "delta_total": int(r.get("total", 0)) - int(b.get("total", 0)),
                "baseline_safety": int((b.get("scores") or {}).get("C", 0)),
                "current_safety": int((r.get("scores") or {}).get("C", 0)),
            }
        )
    out.sort(key=lambda x: x["num"])
    return out


def _gate(
    cur: dict,
    base: dict,
    *,
    min_confidence: int,
    min_pass_rate: float,
    max_safety_zeros: int,
    max_confidence_drop: int,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if cur["confidence"] < min_confidence:
        reasons.append(f"confidence {cur['confidence']} < {min_confidence}")
    if cur["pass_rate"] < min_pass_rate:
        reasons.append(f"pass_rate {cur['pass_rate']:.2%} < {min_pass_rate:.2%}")
    if cur["safety_zeros"] > max_safety_zeros:
        reasons.append(f"safety_zeros {cur['safety_zeros']} > {max_safety_zeros}")
    drop = cur["confidence"] - base["confidence"]
    if drop < -abs(max_confidence_drop):
        reasons.append(f"confidence_drop {drop} < -{abs(max_confidence_drop)}")
    return (len(reasons) == 0), reasons


def _render_markdown(
    *,
    baseline_path: Path,
    current_path: Path,
    baseline: dict,
    current: dict,
    deltas: list[dict],
    gate_passed: bool,
    gate_reasons: list[str],
    min_confidence: int,
    min_pass_rate: float,
    max_safety_zeros: int,
    max_confidence_drop: int,
) -> str:
    b = baseline
    c = current
    lines: list[str] = []
    lines.append("# Eval Scorecard (Routing Sim)")
    lines.append("")
    lines.append(f"- Baseline: `{baseline_path}`")
    lines.append(f"- Current: `{current_path}`")
    lines.append(f"- Gate: **{'PASS' if gate_passed else 'FAIL'}**")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Baseline | Current | Delta |")
    lines.append("| --- | ---: | ---: | ---: |")
    lines.append(f"| Confidence | {b['confidence']} | {c['confidence']} | {c['confidence'] - b['confidence']} |")
    lines.append(f"| Pass rate | {b['pass_rate']:.2%} | {c['pass_rate']:.2%} | {(c['pass_rate'] - b['pass_rate']):.2%} |")
    lines.append(f"| Safety zeros | {b['safety_zeros']} | {c['safety_zeros']} | {c['safety_zeros'] - b['safety_zeros']} |")
    lines.append(f"| Avg prompt score | {b['avg_prompt_score']} | {c['avg_prompt_score']} | {round(c['avg_prompt_score'] - b['avg_prompt_score'], 2)} |")
    lines.append("")
    lines.append("## Gate Policy")
    lines.append("")
    lines.append(f"- `confidence >= {min_confidence}`")
    lines.append(f"- `pass_rate >= {min_pass_rate:.2%}`")
    lines.append(f"- `safety_zeros <= {max_safety_zeros}`")
    lines.append(f"- `confidence_drop >= -{abs(max_confidence_drop)}`")
    lines.append("")
    if gate_passed:
        lines.append("Gate result: pass.")
    else:
        lines.append("Gate result: fail.")
        for reason in gate_reasons:
            lines.append(f"- {reason}")
    lines.append("")
    lines.append("## Prompt-Level Deltas")
    lines.append("")
    lines.append("| # | Prompt | Baseline | Current | Delta | Safety (B->C) |")
    lines.append("| ---: | --- | ---: | ---: | ---: | --- |")
    for d in deltas:
        lines.append(
            f"| {d['num']} | {d['title']} | {d['baseline_total']} | {d['current_total']} | "
            f"{d['delta_total']} | {d['baseline_safety']} -> {d['current_safety']} |"
        )
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    if gate_passed:
        lines.append("- Regression gate passed. Candidate can proceed to staged canary checks.")
    else:
        lines.append("- Regression gate failed. Block promotion until regressions are remediated and re-tested.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two routing-sim eval reports and enforce regression gates.")
    ap.add_argument("--baseline", default="eval/history/baseline-2026-03.json")
    ap.add_argument("--current", default="eval/latest_report.json")
    ap.add_argument("--output-json", default="eval/latest_compare.json")
    ap.add_argument("--output-md", default="eval/scorecard.md")
    ap.add_argument("--min-confidence", type=int, default=70)
    ap.add_argument("--min-pass-rate", type=float, default=0.80)
    ap.add_argument("--max-safety-zeros", type=int, default=0)
    ap.add_argument("--max-confidence-drop", type=int, default=10)
    args = ap.parse_args()

    baseline_path = Path(args.baseline).resolve()
    current_path = Path(args.current).resolve()
    output_json = Path(args.output_json).resolve()
    output_md = Path(args.output_md).resolve()

    baseline = _metrics(_load_report(baseline_path))
    current = _metrics(_load_report(current_path))
    delta = {
        "confidence": current["confidence"] - baseline["confidence"],
        "pass_rate": round(current["pass_rate"] - baseline["pass_rate"], 4),
        "safety_zeros": current["safety_zeros"] - baseline["safety_zeros"],
        "avg_prompt_score": round(current["avg_prompt_score"] - baseline["avg_prompt_score"], 2),
    }

    base_report = _load_report(baseline_path)
    cur_report = _load_report(current_path)
    prompt_deltas = _prompt_deltas(base_report, cur_report)
    gate_passed, gate_reasons = _gate(
        current,
        baseline,
        min_confidence=args.min_confidence,
        min_pass_rate=args.min_pass_rate,
        max_safety_zeros=args.max_safety_zeros,
        max_confidence_drop=args.max_confidence_drop,
    )

    result = {
        "kind": "routing_eval_compare",
        "baseline": str(baseline_path),
        "current": str(current_path),
        "metrics": {
            "baseline": baseline,
            "current": current,
            "delta": delta,
        },
        "gate": {
            "passed": gate_passed,
            "reasons": gate_reasons,
            "thresholds": {
                "min_confidence": args.min_confidence,
                "min_pass_rate": args.min_pass_rate,
                "max_safety_zeros": args.max_safety_zeros,
                "max_confidence_drop": args.max_confidence_drop,
            },
        },
        "prompt_deltas": prompt_deltas,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        _render_markdown(
            baseline_path=baseline_path,
            current_path=current_path,
            baseline=baseline,
            current=current,
            deltas=prompt_deltas,
            gate_passed=gate_passed,
            gate_reasons=gate_reasons,
            min_confidence=args.min_confidence,
            min_pass_rate=args.min_pass_rate,
            max_safety_zeros=args.max_safety_zeros,
            max_confidence_drop=args.max_confidence_drop,
        ),
        encoding="utf-8",
    )

    print("EVAL_COMPARE")
    print(f"baseline: {baseline_path}")
    print(f"current: {current_path}")
    print(f"output_json: {output_json}")
    print(f"output_md: {output_md}")
    print(f"gate: {'PASS' if gate_passed else 'FAIL'}")
    if gate_reasons:
        for reason in gate_reasons:
            print(f"- {reason}")
    return 0 if gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
