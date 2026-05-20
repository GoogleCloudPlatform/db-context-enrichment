#!/usr/bin/env python3
"""Mirror a local wiki tree to a GCS bucket.

Thin wrapper around `gcloud storage rsync` so the skill can persist
generated wikis to GCS. Auth uses the same gcloud / ADC stack the rest
of the skill uses — no separate credentials needed.

Usage:
    python3 scripts/gcs_upload.py \\
        --local-dir=./customer-context/wikis \\
        --gcs-uri=gs://bucket-name/optional/prefix \\
        [--delete-extra] [--dry-run]

Notes:
- --gcs-uri must start with gs:// and may include a sub-prefix.
- --delete-extra mirrors semantics: removes remote files that don't
  exist locally. Off by default to avoid surprises.
- --dry-run prints what would change without writing anything to GCS.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--local-dir", required=True, help="Local directory to upload")
    p.add_argument("--gcs-uri", required=True, help="Destination, e.g. gs://bucket/prefix")
    p.add_argument("--delete-extra", action="store_true",
                   help="Remove remote files that don't exist locally")
    p.add_argument("--dry-run", action="store_true", help="Show what would change; don't upload")
    args = p.parse_args()

    local = Path(args.local_dir).resolve()
    if not local.is_dir():
        die(f"--local-dir does not exist or is not a directory: {local}")

    if not args.gcs_uri.startswith("gs://"):
        die(f"--gcs-uri must start with gs:// (got: {args.gcs_uri})")

    if not shutil.which("gcloud"):
        die("`gcloud` CLI not on PATH. Install Google Cloud SDK and `gcloud auth login`.")

    cmd = ["gcloud", "storage", "rsync", "--recursive", str(local), args.gcs_uri]
    if args.delete_extra:
        cmd.append("--delete-unmatched-destination-objects")
    if args.dry_run:
        cmd.append("--dry-run")

    started_at = time.time()
    print(f"running: {' '.join(cmd)}", file=sys.stderr)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    duration_s = time.time() - started_at

    file_count = sum(1 for _ in local.rglob("*") if _.is_file())
    total_bytes = sum(p.stat().st_size for p in local.rglob("*") if p.is_file())

    result = {
        "local_dir": str(local),
        "gcs_uri": args.gcs_uri,
        "delete_extra": args.delete_extra,
        "dry_run": args.dry_run,
        "exit_code": proc.returncode,
        "duration_seconds": round(duration_s, 2),
        "local_file_count": file_count,
        "local_total_bytes": total_bytes,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
    }

    print(json.dumps(result, indent=2))
    sys.exit(proc.returncode)


def die(msg: str):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
