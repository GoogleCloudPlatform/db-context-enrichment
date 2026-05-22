#!/usr/bin/env python3
"""Live fetchers for source_diff.py --live mode.

Each source in `source_manifest.json` was originally captured from some
external system: a Google Doc body, a Google Sheet, a BigQuery schema, etc.
The local on-disk source `.md` file is a snapshot of that external state at
some moment. Live drift detection means: re-fetch the external state RIGHT
NOW and compare it to what the snapshot says.

This module dispatches a manifest entry to the appropriate fetcher, runs
the fetch, and returns a `LiveSnapshot` (or raises `LiveFetchError`).

What's wrapped in v1:
  - Google Docs (via the existing scripts/gdocs_extract.py)
  - Google Sheets (via scripts/gsheets_extract.py)
  - BigQuery schemas (`bq show --schema`)
  - BigQuery dataset listings (`bq ls`)

Skipped in v1 (returns SKIP, not an error):
  - BigQuery JOBS_BY_PROJECT (volatile by design — every fetch differs
    because the WHERE clause uses NOW())
  - Dataplex (`gcloud dataplex *`) — complex, defer to a later phase
  - Anything else not pattern-matched

The fetcher functions return the canonical TEXT representation of the
live state. source_diff normalizes both sides (live + on-disk) before
comparing so trivial whitespace differences don't trigger false drift.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Where the original capture scripts live. Resolve relative to this file
# so we work whether the skill is symlinked or run in-tree.
_SCRIPTS_DIR = Path(__file__).resolve().parent

DEFAULT_TIMEOUT_SEC = 60


# ---------------- Errors and result types ----------------

class LiveFetchError(Exception):
    """Raised when a live fetch fails. .kind is one of:
      NOT_FOUND   - source no longer exists at origin (404, deleted file)
      AUTH_FAILED - credentials missing/invalid for this source
      TIMEOUT     - fetch ran past DEFAULT_TIMEOUT_SEC
      OTHER       - any other failure (network, parse, unexpected output)
    """
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass
class LiveSnapshot:
    """Result of a successful live fetch."""
    fetcher: str       # "gdoc" / "gsheet" / "bq_schema" / "bq_dataset_list"
    source_uri: str    # for diagnostics
    body: str          # canonical text body of the live state


@dataclass
class FetchOutcome:
    """Aggregate result for one manifest entry. Exactly one of
    snapshot/error/skip is non-None."""
    source_path: str
    snapshot: LiveSnapshot | None = None
    error: LiveFetchError | None = None
    skip_reason: str | None = None


# ---------------- Volatile / unsupported skip patterns ----------------

# Lineage commands matching these patterns are by-design volatile or
# unsupported. We return a "skipped" outcome so they don't pollute the
# drift report with false positives or perpetual fetch failures.
SKIP_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"INFORMATION_SCHEMA\.JOBS", re.IGNORECASE),
     "volatile by design (JOBS_BY_PROJECT uses NOW() — every fetch differs)"),
    (re.compile(r"gcloud\s+dataplex", re.IGNORECASE),
     "no live fetcher for Dataplex in this version"),
    (re.compile(r"bq\s+ls\s+--transfer_config", re.IGNORECASE),
     "no live fetcher for transfer configs in this version"),
]


# ---------------- Fetchers ----------------

def _run(cmd: list[str], timeout: int = DEFAULT_TIMEOUT_SEC) -> str:
    """Shell out, return stdout, raise LiveFetchError on failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise LiveFetchError("TIMEOUT", f"command timed out after {timeout}s: {cmd[0]}")
    except FileNotFoundError as e:
        raise LiveFetchError("OTHER", f"command not found: {e}")
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").lower()
        if any(s in err for s in (
            "not found", "404", "no such", "does not exist",
            "could not find", "doesn't exist",
        )):
            raise LiveFetchError("NOT_FOUND", proc.stderr.strip()[:300])
        if any(s in err for s in (
            "credentials", "permission denied", "unauthorized",
            "auth", "403", "invalid_grant",
        )):
            raise LiveFetchError("AUTH_FAILED", proc.stderr.strip()[:300])
        raise LiveFetchError(
            "OTHER",
            f"exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]}",
        )
    return proc.stdout


def fetch_gdoc(doc_id: str, max_chars: int = 15000) -> str:
    """Re-fetch a Google Doc via gdocs_extract.py. Returns the doc body
    as markdown (matches what the original capture wrote to disk)."""
    script = _SCRIPTS_DIR / "gdocs_extract.py"
    out = _run([
        sys.executable, str(script),
        f"--doc-id={doc_id}",
        f"--max-chars={max_chars}",
    ])
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        raise LiveFetchError("OTHER", f"gdocs_extract returned non-JSON: {e}")
    body = (payload.get("body") or "").rstrip()
    if not body:
        raise LiveFetchError("OTHER", "gdocs_extract returned empty body")
    return body


def fetch_gsheet(sheet_id: str, rows_per_tab: int = 15) -> str:
    """Re-fetch a Google Sheet via gsheets_extract.py. Returns a canonical
    text representation: one block per tab, header + sample rows."""
    script = _SCRIPTS_DIR / "gsheets_extract.py"
    out = _run([
        sys.executable, str(script),
        f"--sheet-id={sheet_id}",
        f"--rows-per-tab={rows_per_tab}",
    ])
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as e:
        raise LiveFetchError("OTHER", f"gsheets_extract returned non-JSON: {e}")
    parts: list[str] = []
    for tab in payload.get("tabs", []):
        parts.append(f"## Tab: {tab.get('title', '')}")
        header = tab.get("header") or []
        parts.append("Header: " + " | ".join(str(h) for h in header))
        for row in tab.get("sample_rows") or []:
            parts.append(" | ".join(str(c) for c in row))
        parts.append("")
    body = "\n".join(parts).rstrip()
    if not body:
        raise LiveFetchError("OTHER", "gsheets_extract returned no tabs")
    return body


def fetch_bq_schema(table_fqn: str) -> str:
    """Re-fetch a BigQuery table schema via `bq show --schema`. Returns
    the prettyjson schema text. table_fqn is `project:dataset.table` or
    `project.dataset.table`."""
    out = _run([
        "bq", "show", "--schema", "--format=prettyjson", table_fqn,
    ])
    return out.rstrip()


def fetch_bq_dataset_list(project_id: str) -> str:
    """Re-fetch the dataset list for a project via `bq ls`. Returns the
    prettyjson listing text."""
    out = _run([
        "bq", "ls", f"--project_id={project_id}", "--format=prettyjson",
    ])
    return out.rstrip()


# ---------------- Dispatch ----------------

# Each entry: (lineage_pattern, uri_pattern, fetcher_name, args_extractor).
# args_extractor takes (lineage_match | None, uri_match | None) and returns
# kwargs for the fetcher. We try lineage first since it carries the exact
# command + args; fall back to URI if lineage didn't match.
_DISPATCH: list[dict] = [
    {
        "name": "gdoc",
        "lineage": re.compile(r"gdocs_extract\.py.*?--doc-id=([\w-]+)"),
        "uri": re.compile(r"docs\.google\.com/document/d/([\w-]+)"),
        "fetcher": fetch_gdoc,
        "args": lambda lm, um: {"doc_id": (lm or um).group(1)},
    },
    {
        "name": "gsheet",
        "lineage": re.compile(r"gsheets_extract\.py.*?--sheet-id=([\w-]+)"),
        "uri": re.compile(r"docs\.google\.com/spreadsheets/d/([\w-]+)"),
        "fetcher": fetch_gsheet,
        "args": lambda lm, um: {"sheet_id": (lm or um).group(1)},
    },
    {
        # bq show --schema project:dataset.table   (or project.dataset.table)
        "name": "bq_schema",
        "lineage": re.compile(
            r"bq\s+show\s+--schema.*?\s([\w-]+[:\.][\w_]+\.[\w_]+)"
        ),
        "uri": re.compile(
            r"BigQuery\s+(?:table\s+)?[`]?([\w-]+[:\.][\w_]+\.[\w_]+)[`]?",
            re.IGNORECASE,
        ),
        "fetcher": fetch_bq_schema,
        "args": lambda lm, um: {"table_fqn": (lm or um).group(1).replace(":", ".")},
    },
    {
        "name": "bq_dataset_list",
        "lineage": re.compile(r"bq\s+ls\s+--project_id=([\w-]+)"),
        "uri": re.compile(r"datasets?\s+in\s+[`]?([\w-]+)[`]?", re.IGNORECASE),
        "fetcher": fetch_bq_dataset_list,
        "args": lambda lm, um: {"project_id": (lm or um).group(1)},
    },
]


def _check_skip(lineage: str, uri: str) -> str | None:
    blob = f"{lineage}\n{uri}"
    for pat, reason in SKIP_PATTERNS:
        if pat.search(blob):
            return reason
    return None


def dispatch(source_record: dict) -> FetchOutcome:
    """Look at one source_manifest entry and either fetch it live or skip.

    source_record fields used:
      - path: wiki-relative path of the source file (used for the outcome key)
      - source_uri: the original URI (e.g. "Google Doc — https://...")
      - lineage: how the source was originally captured (e.g. "python3 ...
        gdocs_extract.py --doc-id=...")
    """
    path = source_record.get("path", "")
    lineage = source_record.get("lineage", "") or ""
    uri = source_record.get("source_uri", "") or ""

    skip = _check_skip(lineage, uri)
    if skip:
        return FetchOutcome(source_path=path, skip_reason=skip)

    for entry in _DISPATCH:
        lm = entry["lineage"].search(lineage)
        um = entry["uri"].search(uri) if not lm else None
        if not lm and not um:
            continue
        try:
            kwargs = entry["args"](lm, um)
            body = entry["fetcher"](**kwargs)
            return FetchOutcome(source_path=path, snapshot=LiveSnapshot(
                fetcher=entry["name"], source_uri=uri or lineage, body=body,
            ))
        except LiveFetchError as e:
            return FetchOutcome(source_path=path, error=e)
        except Exception as e:
            return FetchOutcome(
                source_path=path,
                error=LiveFetchError("OTHER", f"{type(e).__name__}: {e}"),
            )

    return FetchOutcome(
        source_path=path,
        skip_reason="no live fetcher matched (URI/lineage didn't match any registered pattern)",
    )


# ---------------- Normalization for comparison ----------------

_BLOCKQUOTE_PREFIX = re.compile(r"^\s*>\s?", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


def normalize_for_compare(text: str) -> str:
    """Strip blockquote markers, collapse whitespace, lowercase. Used on
    both the live body AND the on-disk gist body so trivial formatting
    differences don't trigger false drift."""
    s = _BLOCKQUOTE_PREFIX.sub("", text)
    s = _WHITESPACE.sub(" ", s)
    return s.strip().lower()


def extract_on_disk_body(source_md_text: str) -> str:
    """Pull the GIST CONTENT out of a source `.md` file — everything under
    the `# Gists` heading, with section subheadings preserved. Used as the
    'what we have on disk' side of the live-vs-disk comparison."""
    m = re.search(
        r"^#\s+Gists\s*$(.+?)(?=^#\s+\w|\Z)",
        source_md_text, re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip()
