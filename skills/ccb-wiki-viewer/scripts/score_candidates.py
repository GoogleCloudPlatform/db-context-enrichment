#!/usr/bin/env python3
"""Score each candidate by how many wiki gaps it would close.

Reads each candidate's sources.json (the evidence list — gist files the
candidate clusters over) and each customer wiki's GAPS.json. A candidate
"bridges" a gap when its evidence overlaps with the gap's source files.

Scoring formula (depth-weighted):

    coverage_fraction = |candidate_evidence ∩ gap_sources| / |gap_sources|
    gap_contribution  = severity_weight(gap) × coverage_fraction
    bridge_score      = sum of gap_contribution over all gaps

Severity weights:  high = 3,  medium = 2,  low = 1

So a candidate that fully covers one HIGH gap contributes 3.0; one that
barely touches the same HIGH (1 of 5 sources) contributes 0.6. This
means a high-confidence candidate that deeply addresses 1 HIGH gap
correctly outranks a noisy one that grazes 5 LOWs.

Writes back to each sources.json:
    bridge_score: float          # sum of (severity × coverage_fraction)
    gaps_addressed: list[dict]   # [{gap_id, severity, coverage}, ...]

Then re-runs `scan_candidates._regenerate_index` so the Candidates tab's
landing page shows the new column and sorts high-bridge candidates first.

This script is mechanical — no LLM. Designed to run after every
scan_candidates rescan or ticket-to-candidate generation.

Usage:
    python3 score_candidates.py \\
        --wikis-root=examples/sample_context_center/wikis \\
        --candidates-dir=examples/sample_context_center/candidates
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import from sibling scan_candidates.py to reuse the index regenerator.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_candidates import _regenerate_index  # noqa: E402

SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def find_wiki_gaps(wikis_root: Path) -> list[tuple[str, list[dict]]]:
    """For every customer wiki under wikis_root, find its GAPS.json (if any)
    and return (wiki_relpath, gaps).

    wiki_relpath is the wiki root's path relative to wikis_root, e.g.
    `acme/context-repo-building`. We need this to translate per-wiki gap
    source paths (like `personal_context/sources/foo.md`) into the
    wikis-root-relative form that candidate evidence uses.
    """
    out: list[tuple[str, list[dict]]] = []
    for gaps_path in sorted(wikis_root.rglob("GAPS.json")):
        wiki_root = gaps_path.parent
        try:
            data = json.loads(gaps_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rel = wiki_root.resolve().relative_to(wikis_root.resolve()).as_posix()
        out.append((rel, data.get("gaps", [])))
    return out


def score_candidate(
    candidate_evidence: list[str],
    wikis_with_gaps: list[tuple[str, list[dict]]],
) -> tuple[float, list[dict]]:
    """Return (bridge_score, [{gap_id, severity, coverage}, ...]).

    Score is depth-weighted: a candidate gets credit proportional to how
    much of each gap it actually covers, not just whether it touches the
    gap at all.
    """
    score = 0.0
    addressed: list[dict] = []
    ev_set = set(candidate_evidence or [])
    for wiki_rel, gaps in wikis_with_gaps:
        for g in gaps:
            gap_sources = {
                f"{wiki_rel}/{s.split('#', 1)[0]}"
                for s in g.get("sources", [])
            }
            if not gap_sources:
                continue
            overlap = ev_set & gap_sources
            if not overlap:
                continue
            coverage = len(overlap) / len(gap_sources)
            severity = g.get("severity", "low")
            contribution = SEVERITY_WEIGHT.get(severity, 0) * coverage
            score += contribution
            addressed.append({
                "gap_id": g["id"],
                "severity": severity,
                "coverage": round(coverage, 2),
            })
    return round(score, 2), addressed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wikis-root", required=True)
    ap.add_argument("--candidates-dir", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wikis_root = Path(args.wikis_root).resolve()
    if not wikis_root.is_dir():
        sys.exit(f"--wikis-root not a directory: {wikis_root}")
    candidates_dir = Path(args.candidates_dir).resolve()
    if not candidates_dir.is_dir():
        sys.exit(f"--candidates-dir not a directory: {candidates_dir}")

    wikis_with_gaps = find_wiki_gaps(wikis_root)

    n_scored = 0
    high_bridge = 0
    for sub in sorted(candidates_dir.iterdir()):
        if not sub.is_dir():
            continue
        sj = sub / "sources.json"
        if not sj.is_file():
            continue
        try:
            meta = json.loads(sj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        evidence = meta.get("evidence") or []
        score, addressed = score_candidate(evidence, wikis_with_gaps)
        meta["bridge_score"] = score
        meta["gaps_addressed"] = addressed
        sj.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        n_scored += 1
        if score >= 3.0:
            high_bridge += 1

    # Re-render index.md so the new column is visible.
    _regenerate_index(candidates_dir)

    if not args.quiet:
        print(
            f"scored {n_scored} candidate(s); {high_bridge} have bridge_score >= 3",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
