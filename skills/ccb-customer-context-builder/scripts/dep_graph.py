#!/usr/bin/env python3
"""Build the section → claims → sources dependency graph for one wiki.

Reads `claims_index.json` (from claims_sidecar.py) and
`source_manifest.json` (from build_manifest.py); writes `dep_graph.json`
at the wiki root. The graph is the spine that everything downstream
consumes:

  - gap_check.py uses it to compute the "explicit" wiki graph
    (narrative section → cited source).
  - The wiki-viewer side panel uses it to surface "this page is cited
    in N other pages" backlinks (TODO: not rendered yet).
  - rebuild_plan.py uses it as the blast-radius lookup for a changed
    source — drift × dep_graph → which narrative sections need to be
    re-derived.

Schema:
    {
      "schema": "dep_graph.v1",
      "wiki_root": "...",
      "nodes": {
        "<file>": { "kind": "narrative"|"source", "claims": N, "sources_cited": M }
      },
      "edges": [
        { "from": "<narrative>", "to": "<source>", "claim_id": "...", "tag": "EXTRACTED" }
      ]
    }

Usage:
    python3 dep_graph.py --wiki-root=path/to/customer
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_json(p: Path) -> dict | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"warning: {p} is not valid JSON: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    claims_index = load_json(wiki_root / "claims_index.json")
    source_manifest = load_json(wiki_root / "source_manifest.json")
    if claims_index is None:
        sys.exit("claims_index.json missing — run claims_sidecar.py first")
    if source_manifest is None:
        sys.exit("source_manifest.json missing — run build_manifest.py first")

    # Per-file claim sidecars carry the actual claim records.
    claims_by_file: dict[str, list[dict]] = {}
    for rel in claims_index.get("files_with_claims", []):
        sidecar = wiki_root / (rel + ".claims.json")
        sc = load_json(sidecar)
        if sc:
            claims_by_file[rel] = sc.get("claims", [])

    source_paths = {s["path"] for s in source_manifest.get("sources", [])}

    nodes: dict[str, dict] = {}
    for rel in source_paths:
        nodes[rel] = {"kind": "source", "claims": 0, "sources_cited": 0}
    for rel, claims in claims_by_file.items():
        nodes.setdefault(rel, {"kind": "narrative", "claims": 0, "sources_cited": 0})
        nodes[rel]["claims"] = len(claims)

    edges: list[dict] = []
    cited_by: dict[str, set[str]] = defaultdict(set)
    for rel, claims in claims_by_file.items():
        cites_for_file: set[str] = set()
        for claim in claims:
            for src in claim.get("sources", []):
                # Strip #anchor for graph purposes.
                src_path = src.split("#", 1)[0]
                edges.append({
                    "from": rel,
                    "to": src_path,
                    "claim_id": claim.get("id"),
                    "tag": claim.get("tag"),
                })
                cites_for_file.add(src_path)
                cited_by[src_path].add(rel)
        nodes[rel]["sources_cited"] = len(cites_for_file)

    # Add a backlink count to source nodes so the side panel can show
    # "cited in N narrative files" without recomputing.
    for src_path, citers in cited_by.items():
        if src_path in nodes:
            nodes[src_path]["cited_by_count"] = len(citers)
            nodes[src_path]["cited_by"] = sorted(citers)

    payload = {
        "schema": "dep_graph.v1",
        "wiki_root": wiki_root.name,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    out_path = wiki_root / "dep_graph.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not args.quiet:
        print(
            f"dep graph: {len(nodes)} nodes, {len(edges)} edges → {out_path.name}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
