#!/usr/bin/env python3
"""Mark a drift entry as acknowledged so it stops appearing in DRIFT.md.

Acknowledged IDs are persisted to `<wiki>/.drift-acknowledged.json`.
`source_diff.py` reads this file and filters acknowledged IDs out of the
next report.

Acknowledgement is by drift ID (e.g. drift-C-1a2b3c4d), which is stable
across runs as long as the (kind, source path) pair is unchanged. If the
same source drifts again later in a different way (e.g. it's deleted
after having been changed), the new entry has a different ID and will
re-appear.

Usage:
    # Acknowledge one entry
    python3 acknowledge_drift.py --wiki-root=path --drift-id=drift-C-1a2b3c4d

    # Acknowledge several at once
    python3 acknowledge_drift.py --wiki-root=path --drift-id=drift-C-1a2b3c4d --drift-id=drift-D-...

    # Wipe all acknowledgements (start fresh)
    python3 acknowledge_drift.py --wiki-root=path --reset
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ACK_FILENAME = ".drift-acknowledged.json"


def load(path: Path) -> dict:
    if not path.is_file():
        return {"schema": "drift_ack.v1", "acknowledged_ids": [], "history": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema": "drift_ack.v1", "acknowledged_ids": [], "history": []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument("--drift-id", action="append", default=[],
                    help="Drift ID to acknowledge (repeatable).")
    ap.add_argument("--note", default="",
                    help="Optional human note recorded alongside the ack.")
    ap.add_argument("--reset", action="store_true",
                    help="Clear all acknowledgements.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")
    ack_path = wiki_root / ACK_FILENAME

    if args.reset:
        ack_path.write_text(
            json.dumps(
                {"schema": "drift_ack.v1", "acknowledged_ids": [], "history": []},
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"reset {ack_path.name} (no acks remain)", file=sys.stderr)
        return 0

    if not args.drift_id:
        sys.exit("must pass at least one --drift-id (or --reset).")

    ack = load(ack_path)
    existing = set(ack.get("acknowledged_ids", []))
    new_ids = [d for d in args.drift_id if d not in existing]
    existing.update(new_ids)
    ack["acknowledged_ids"] = sorted(existing)
    ack.setdefault("history", []).append({
        "ack_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ids": args.drift_id,
        "note": args.note,
    })
    ack_path.write_text(
        json.dumps(ack, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not args.quiet:
        print(
            f"acknowledged {len(new_ids)} new drift id(s); "
            f"{len(existing)} total acks recorded → {ack_path.name}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
