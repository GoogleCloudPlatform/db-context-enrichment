#!/usr/bin/env python3
"""Compute an incremental-rebuild plan from a drift report + dep graph.

Reads DRIFT.json + dep_graph.json and emits rebuild_plan.json: a list of
narrative sections that need re-derivation because their cited sources
drifted, plus the agent that owns each section. The orchestrator can hand
this plan to a focused sub-agent to do surgical re-extraction instead of
rebuilding the whole wiki.

This script only PLANS. It does not run the rebuild — the actual surgical
re-extraction is an LLM-driven step the orchestrator does next, scoped
exactly to what this plan lists.

Schema:
    {
      "schema": "rebuild_plan.v1",
      "wiki_root": "...",
      "generated_at": "...",
      "drift_summary": {
        "changed": N, "deleted": N, "new": N,
        "high": N, "medium": N, "low": N
      },
      "actions": [
        {
          "section": "fact_orders_daily/lineage.md",
          "agent": "warehouse_agent",
          "reason": "cites 1 changed source(s) with EXTRACTED claim(s): ...",
          "drifted_sources": ["personal_context/sources/...md"],
          "claims_to_revalidate": ["c1", "c4"],
          "priority": "high"
        }
      ],
      "skip_reasons": [
        {"section": "...", "reason": "no drifted source cited"}
      ]
    }

Usage:
    python3 rebuild_plan.py --wiki-root=path/to/customer
    python3 rebuild_plan.py --wiki-root=... --threshold=medium  # skip low-severity drift
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


# Heuristic: which agent owns which kind of file. The orchestrator can
# override per-customer; this is a sensible default that matches the
# customer-context-builder agent layout.
def owning_agent(section: str) -> str:
    if section.startswith("personal_context/"):
        return "personal_context_agent"
    return "warehouse_agent"


def load_json(p: Path) -> dict | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument(
        "--threshold", choices=("high", "medium", "low"), default="low",
        help="Minimum drift severity to trigger a rebuild action. "
             "Default: low (rebuild for any drift).",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    drift = load_json(wiki_root / "DRIFT.json")
    if drift is None:
        sys.exit("DRIFT.json missing — run source_diff.py first.")
    dep_graph = load_json(wiki_root / "dep_graph.json")
    if dep_graph is None:
        sys.exit("dep_graph.json missing — run dep_graph.py first.")

    threshold_rank = SEVERITY_RANK[args.threshold]

    # source -> [drift entries that affect it]
    drifted_sources: dict[str, list[dict]] = defaultdict(list)
    for d in drift.get("drifts", []):
        if SEVERITY_RANK.get(d.get("severity", "low"), 0) < threshold_rank:
            continue
        drifted_sources[d["source"]].append(d)

    # narrative_section -> {drifted_sources, claims_to_revalidate, priority}
    actions: dict[str, dict] = {}
    skip_reasons: list[dict] = []

    # Walk dep_graph edges: each edge is (narrative -> source).
    # For each narrative, collect the drifted sources it cites.
    narrative_to_drifted: dict[str, dict[str, list[dict]]] = defaultdict(dict)
    narrative_to_claims: dict[str, set[str]] = defaultdict(set)
    for edge in dep_graph.get("edges", []):
        narrative = edge["from"]
        source = edge["to"]
        if source in drifted_sources:
            narrative_to_drifted[narrative].setdefault(source, drifted_sources[source])
            narrative_to_claims[narrative].add(edge["claim_id"])

    for narrative, srcs in narrative_to_drifted.items():
        # Priority = highest severity among the drifts affecting this section.
        max_rank = 0
        max_severity = "low"
        bands_seen: set[str] = set()
        kinds_seen: set[str] = set()
        for entries in srcs.values():
            for d in entries:
                r = SEVERITY_RANK.get(d.get("severity", "low"), 0)
                if r > max_rank:
                    max_rank, max_severity = r, d["severity"]
                kinds_seen.add(d["kind"])
                for ci in d.get("claims_impacted", []):
                    if ci.get("file") == narrative:
                        bands_seen.add(ci.get("tag", ""))

        reason_parts = []
        for kind in sorted(kinds_seen):
            n = sum(1 for entries in srcs.values()
                    for d in entries if d["kind"] == kind)
            reason_parts.append(f"{n} {kind}")
        if bands_seen:
            reason_parts.append(f"bands cited from this section: {', '.join(sorted(bands_seen))}")
        reason = "cites drifted source(s) — " + "; ".join(reason_parts)

        actions[narrative] = {
            "section": narrative,
            "agent": owning_agent(narrative),
            "reason": reason,
            "drifted_sources": sorted(srcs.keys()),
            "claims_to_revalidate": sorted(narrative_to_claims[narrative]),
            "priority": max_severity,
        }

    # Sections that have claims but no drift → skip.
    for node, info in dep_graph.get("nodes", {}).items():
        if info.get("kind") != "narrative":
            continue
        if node in actions:
            continue
        if info.get("claims", 0) == 0:
            continue
        skip_reasons.append({
            "section": node,
            "reason": "no drifted source cited",
        })

    # Sort actions: priority desc, then section path.
    sorted_actions = sorted(
        actions.values(),
        key=lambda a: (-SEVERITY_RANK.get(a["priority"], 0), a["section"]),
    )

    payload = {
        "schema": "rebuild_plan.v1",
        "wiki_root": wiki_root.name,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold": args.threshold,
        "drift_summary": {
            **drift.get("by_kind", {}),
            **drift.get("by_severity", {}),
        },
        "action_count": len(sorted_actions),
        "actions": sorted_actions,
        "skip_count": len(skip_reasons),
        "skip_reasons": skip_reasons,
    }
    out = wiki_root / "rebuild_plan.json"
    out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not args.quiet:
        print(
            f"rebuild plan: {len(sorted_actions)} action(s), "
            f"{len(skip_reasons)} section(s) skipped → {out.name}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
