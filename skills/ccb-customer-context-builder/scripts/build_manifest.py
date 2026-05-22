#!/usr/bin/env python3
"""Build a source manifest with content hashes for one customer wiki.

Walks every `*.md` under any `sources/` directory in the wiki, hashes the
file's content (sha256), and emits `source_manifest.json` at the wiki
root. The manifest is the foundation for:

  - Coverage gap detection (does the source have a fact the wiki misses?)
  - Drift detection (compare a fresh manifest against the cached one to
    find sources that changed under us)
  - Incremental rebuild (cache key = content hash)

This script reads what's already on disk; it does NOT re-fetch from BigQuery
or Drive. The agents' `# Retrieved from` blocks already contain the source
URI, lineage, and retrieval timestamp; we add the hash so a future run can
diff.

Usage:
    python3 build_manifest.py --wiki-root=path/to/customer

    # Also pin a copy as a named baseline that source_diff --baseline can
    # compare against later. The next build_manifest run won't overwrite
    # snapshots — they're permanent until you delete them.
    python3 build_manifest.py --wiki-root=... --snapshot=qbr-2026-q2 \\
                              --note="Pinned at Q2 QBR review"
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

SOURCE_DIR_NAME = "sources"

# Pull common metadata fields out of the # Retrieved from block.
META_KEYS = ("Source", "Title", "Lineage", "Absolute path",
             "Last modified", "Retrieved at", "Content hash")
META_RE_TPL = r"^[-*]\s+\*\*{key}:\*\*\s+(.+?)\s*$"


def parse_retrieved_block(text: str) -> dict[str, str]:
    """Pull the metadata bullets out of the `# Retrieved from` section."""
    out: dict[str, str] = {}
    # Slice out everything between # Retrieved from and the next H1.
    m = re.search(
        r"^#\s+Retrieved from\s*$(.+?)(?=^#\s+\w|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    if not m:
        return out
    block = m.group(1)
    for key in META_KEYS:
        km = re.search(
            META_RE_TPL.format(key=re.escape(key)),
            block, re.MULTILINE,
        )
        if km:
            out[key] = km.group(1).strip().strip("`").strip()
    return out


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def collect_source_files(wiki_root: Path) -> list[Path]:
    """Every *.md under any */sources/ subdir, excluding sources/index.md."""
    out: list[Path] = []
    for src_dir in wiki_root.rglob(SOURCE_DIR_NAME):
        if not src_dir.is_dir():
            continue
        for p in sorted(src_dir.glob("*.md")):
            if p.name == "index.md":
                continue
            out.append(p)
    return out


_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify_snapshot_name(s: str) -> str:
    """Conservative filename slug for snapshot names. Keeps dots so e.g.
    `qbr-2026.q2` survives unchanged; collapses everything else to `-`.
    Empty after slugification → error."""
    s = _SLUG_RE.sub("-", s).strip("-.")
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument(
        "--snapshot", default=None,
        help="If set, also write a pinned copy of the manifest at "
             "<wiki>/snapshots/<name>.json. Future build_manifest runs "
             "won't overwrite it. source_diff.py --baseline=<name> can "
             "then diff against this snapshot.",
    )
    ap.add_argument(
        "--note", default="",
        help="Optional human note recorded in the snapshot file. Only "
             "used when --snapshot is set.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    entries: list[dict] = []
    for sf in collect_source_files(wiki_root):
        rel = sf.relative_to(wiki_root).as_posix()
        text = sf.read_text(encoding="utf-8", errors="replace")
        meta = parse_retrieved_block(text)
        # Hash the file's full content (gist + retrieved-from). We could hash
        # only the gists, but using the whole file means edits to the metadata
        # block (e.g. a re-run that pulls fresh content) also bump the hash —
        # which is what drift detection wants.
        entries.append({
            "path": rel,
            "sha256": hash_text(text),
            "size": len(text),
            "source_uri": meta.get("Source", ""),
            "lineage": meta.get("Lineage", ""),
            "title": meta.get("Title", ""),
            "last_modified": meta.get("Last modified", ""),
            "retrieved_at": meta.get("Retrieved at", ""),
        })

    payload = {
        "schema": "source_manifest.v1",
        "wiki_root": wiki_root.name,
        "built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_count": len(entries),
        "sources": entries,
    }
    out_path = wiki_root / "source_manifest.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not args.quiet:
        print(f"manifest: {len(entries)} sources hashed → {out_path.name}",
              file=sys.stderr)

    if args.snapshot:
        slug = slugify_snapshot_name(args.snapshot)
        if not slug:
            sys.exit(f"--snapshot name slugifies to empty: {args.snapshot!r}")
        snap_dir = wiki_root / "snapshots"
        snap_dir.mkdir(exist_ok=True)
        snap_path = snap_dir / f"{slug}.json"
        snap_payload = {
            **payload,
            "snapshot_name": slug,
            "snapshot_note": args.note,
            "snapshotted_at": payload["built_at"],
        }
        snap_path.write_text(
            json.dumps(snap_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"snapshot: pinned {len(entries)} sources → {snap_path.relative_to(wiki_root)}",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
