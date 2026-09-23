#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "laya==0.3.5",
#   "huggingface_hub",
# ]
# ///
"""Salt, model-based frustration insights for agent transcripts.

Extracts user-typed messages from Claude Code, Codex, and Opencode, scores each
one with Laya (severity) plus target and trigger-word heuristics, and emits a
console summary plus an HTML report.
"""

import argparse
import sys
from collections import Counter

from saltlib.heuristics import classify_target, find_triggers
from saltlib.report import OUTPUT_HTML, print_summary, render_html
from saltlib.scoring import score_texts
from saltlib.sources import (
    CODEX_HISTORY,
    OPENCODE_DB,
    PROJECTS_DIR,
    SOURCES,
    detect_sources,
    load_messages,
    parse_ts,
)
from saltlib.tuning import label, tune


def analyze(
    include: set[str], min_severity: float, limit: int | None, *, use_cache: bool
):
    messages, total = load_messages(include, limit)
    pasted = sum(1 for m in messages if not m[2])
    messages = [m for m in messages if m[2]]
    scores = score_texts([m[2] for m in messages], use_cache=use_cache)

    findings = []
    seen: set[str] = set()
    model_counts: Counter[str] = Counter()
    for source, project, text, ts in messages:
        sc = scores[text]
        if text not in seen:
            model_counts[sc["model"]] += 1
        if sc["severity"] < min_severity:
            seen.add(text)
            continue
        triggers = find_triggers(text)
        findings.append(
            {
                "source": source,
                "project": project,
                "content": text,
                "ts": parse_ts(ts),
                "is_profane": bool(triggers),
                "target": classify_target(text),
                "severity": sc["severity"],
                "triggers": triggers,
                "model": sc["model"],
                "duplicate": text in seen,
            }
        )
        seen.add(text)

    timestamps = sorted(f["ts"] for f in findings if f["ts"])
    return {
        "findings": findings,
        "unique": [f for f in findings if not f["duplicate"]],
        "total_messages": total,
        "include": include,
        "model_counts": model_counts,
        "min_severity": min_severity,
        "pasted": pasted,
        "date_range": (timestamps[0], timestamps[-1]) if timestamps else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Salt, Laya-based frustration analysis across "
            "Claude Code, Codex, and Opencode."
        )
    )
    parser.add_argument(
        "--no-claude", action="store_true", help="exclude Claude Code transcripts"
    )
    parser.add_argument("--no-codex", action="store_true", help="exclude Codex history")
    parser.add_argument(
        "--no-opencode", action="store_true", help="exclude Opencode data"
    )
    parser.add_argument("--only", choices=SOURCES, help="analyze only one source")
    parser.add_argument(
        "--min-severity",
        type=float,
        default=1.55,
        help="severity cutoff on the 0 to 3 scale (default 1.55)",
    )
    parser.add_argument("--limit", type=int, help="classify only the first N messages")
    parser.add_argument(
        "--no-cache", action="store_true", help="ignore cached classifications"
    )
    parser.add_argument(
        "--label", type=int, metavar="N", help="interactively label N sampled messages"
    )
    parser.add_argument(
        "--tune", action="store_true", help="search cutoffs against your labels"
    )
    args = parser.parse_args()

    available = detect_sources()
    if args.only:
        include = {args.only}
    else:
        excluded = {s for s in SOURCES if getattr(args, f"no_{s}")}
        include = {s for s in SOURCES if available[s] and s not in excluded}

    if not include:
        print("No agent sources available. Looked for:", file=sys.stderr)
        print(f"  Claude Code: {PROJECTS_DIR}", file=sys.stderr)
        print(f"  Codex:       {CODEX_HISTORY}", file=sys.stderr)
        print(f"  Opencode:    {OPENCODE_DB}", file=sys.stderr)
        sys.exit(1)

    if args.label:
        label(include, args.min_severity, args.label)
        return
    if args.tune:
        tune(args.min_severity)
        return

    report = analyze(
        include, args.min_severity, args.limit, use_cache=not args.no_cache
    )
    print_summary(report)
    render_html(report)
    print(f"Report: file://{OUTPUT_HTML}")


if __name__ == "__main__":
    main()
