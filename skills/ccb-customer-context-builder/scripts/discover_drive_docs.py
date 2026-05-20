#!/usr/bin/env python3
"""Discover candidate Drive docs/sheets the user has recently viewed.

Pulls the most recently *viewed-by-me* Google Docs and Sheets, fetches a
short content excerpt for each (or tab list, for sheets), and emits a
JSON list. The orchestrator (Claude) then ranks candidates by relevance
to the customer and presents a picker — discovery itself is unranked
and unfiltered, so the same output can be reused across customers.

Auth: same Drive readonly scope as drive_search.py (ADC).

If the auth principal has no view history (e.g., a service account
without domain-wide delegation), `viewedByMe=true` returns nothing.
The script auto-falls-back to `orderBy=modifiedTime desc` and adds a
warning so the orchestrator knows the signal is weaker.

Output (stdout):
  {
    "candidates": [
      {
        "id": "1abc...",
        "name": "Pipeline Design Doc",
        "kind": "document" | "spreadsheet",
        "modifiedTime": "...",
        "viewedByMeTime": "..." | null,
        "owners": ["jordan@acme.example.com"],
        "webViewLink": "https://docs.google.com/...",
        "parents": [{"id": "...", "name": "Acme - Attribution"}],
        "excerpt": "first ~800 chars of body, or 'Tabs: a, b, c' for sheets"
      }, ...
    ],
    "stats": {"total": N, "with_excerpts": M, "ranking_signal": "viewedByMe" | "modifiedTime"},
    "warnings": [...]
  }
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# httplib2's default socket timeout is short; bump it so parallel doc-body
# fetches don't trip the read timeout under contention.
socket.setdefaulttimeout(30)

MIME = {
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "folder": "application/vnd.google-apps.folder",
}

FILE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, modifiedTime, "
    "viewedByMeTime, webViewLink, owners(emailAddress), parents)"
)


def build_services():
    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/documents.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ]
    )
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive, docs, sheets


def list_recent(drive, mime: str, limit: int, by_viewed: bool) -> Iterator[dict]:
    """Page through Drive ordered by view-time (or fall back to modified-time)."""
    base_q = f"mimeType='{MIME[mime]}' and trashed=false"
    if by_viewed:
        q = f"{base_q} and viewedByMe=true"
        order = "viewedByMeTime desc"
    else:
        q = base_q
        order = "modifiedTime desc"

    page_token = None
    seen = 0
    while seen < limit:
        resp = drive.files().list(
            q=q,
            fields=FILE_FIELDS,
            pageSize=min(100, limit - seen),
            pageToken=page_token,
            orderBy=order,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = resp.get("files", [])
        if not files:
            return
        for f in files:
            yield f
            seen += 1
            if seen >= limit:
                return
        page_token = resp.get("nextPageToken")
        if not page_token:
            return


def fetch_recent_with_fallback(drive, mime: str, limit: int) -> tuple[list[dict], str]:
    """Try viewedByMe first; if zero results, retry with modifiedTime."""
    try:
        files = list(list_recent(drive, mime, limit, by_viewed=True))
        if files:
            return files, "viewedByMe"
    except HttpError:
        pass
    files = list(list_recent(drive, mime, limit, by_viewed=False))
    return files, "modifiedTime"


def resolve_parent(drive, folder_id: str, cache: dict) -> str:
    if folder_id in cache:
        return cache[folder_id]
    try:
        meta = drive.files().get(
            fileId=folder_id,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        cache[folder_id] = meta.get("name", "(unknown)")
    except HttpError:
        cache[folder_id] = "(inaccessible)"
    return cache[folder_id]


def fetch_doc_excerpt(docs_svc, doc_id: str, max_chars: int) -> str:
    """First N chars of doc body, no heading markup. Cheap signal for ranking."""
    try:
        doc = docs_svc.documents().get(documentId=doc_id).execute()
    except HttpError as e:
        return f"(fetch error: HTTP {getattr(e, 'resp', None) and e.resp.status})"
    except Exception as e:  # noqa: BLE001 — surface any auth/quota error to JSON
        return f"(fetch error: {e})"

    parts = []
    total = 0
    for el in doc.get("body", {}).get("content", []):
        p = el.get("paragraph")
        if not p:
            continue
        for sub in p.get("elements", []):
            tr = sub.get("textRun")
            if not tr:
                continue
            text = tr.get("content", "")
            parts.append(text)
            total += len(text)
            if total >= max_chars:
                break
        if total >= max_chars:
            break
    return "".join(parts).strip()[:max_chars]


def fetch_sheet_excerpt(sheets_svc, sheet_id: str) -> str:
    """Tab names — cheap, decent signal (e.g. 'Tabs: uptime, latency, incidents')."""
    try:
        meta = sheets_svc.spreadsheets().get(
            spreadsheetId=sheet_id, includeGridData=False
        ).execute()
    except HttpError as e:
        return f"(fetch error: HTTP {getattr(e, 'resp', None) and e.resp.status})"
    except Exception as e:  # noqa: BLE001
        return f"(fetch error: {e})"
    tabs = [s["properties"]["title"] for s in meta.get("sheets", [])][:10]
    return "Tabs: " + ", ".join(tabs) if tabs else "(no tabs)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-recent", type=int, default=200,
                    help="Cap on how many recent docs+sheets to surface (default 200).")
    ap.add_argument("--max-excerpts", type=int, default=60,
                    help="Cap on how many of the most-recent items get excerpts fetched (default 60).")
    ap.add_argument("--max-chars", type=int, default=800,
                    help="Per-doc excerpt length (default 800 chars).")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="Parallel excerpt fetches (default 8).")
    args = ap.parse_args()

    try:
        drive, docs_svc, sheets_svc = build_services()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"auth failed: {e}"}), file=sys.stderr)
        sys.exit(2)

    warnings: list[str] = []

    half = max(1, args.max_recent // 2)
    docs_files, docs_signal = fetch_recent_with_fallback(drive, "document", half)
    sheets_files, sheets_signal = fetch_recent_with_fallback(drive, "spreadsheet", half)

    # If both fell back, the principal almost certainly has no view history.
    if docs_signal == "modifiedTime" and sheets_signal == "modifiedTime":
        warnings.append(
            "viewedByMe returned no results; falling back to modifiedTime ordering. "
            "If you authed with a service account, run "
            "`gcloud auth application-default login` so discovery can use your view history."
        )
    ranking_signal = docs_signal if docs_signal == sheets_signal else "mixed"

    # Combine + sort by viewed-or-modified time desc, cap to max-recent total.
    all_files = docs_files + sheets_files
    all_files.sort(
        key=lambda f: f.get("viewedByMeTime") or f.get("modifiedTime", ""),
        reverse=True,
    )
    all_files = all_files[: args.max_recent]

    # Resolve parent folder names (cached — many docs share a parent).
    parent_cache: dict[str, str] = {}
    for f in all_files:
        for pid in f.get("parents", []) or []:
            resolve_parent(drive, pid, parent_cache)

    # Fetch excerpts for the top N (most recent of the combined set).
    excerpt_targets = all_files[: args.max_excerpts]
    excerpts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {}
        for f in excerpt_targets:
            mt = f["mimeType"]
            if mt == MIME["document"]:
                futures[ex.submit(fetch_doc_excerpt, docs_svc, f["id"], args.max_chars)] = f["id"]
            elif mt == MIME["spreadsheet"]:
                futures[ex.submit(fetch_sheet_excerpt, sheets_svc, f["id"])] = f["id"]
        for fut in as_completed(futures):
            fid = futures[fut]
            try:
                excerpts[fid] = fut.result()
            except Exception as e:  # noqa: BLE001
                excerpts[fid] = f"(fetch error: {e})"

    candidates = []
    for f in all_files:
        kind = "document" if f["mimeType"] == MIME["document"] else "spreadsheet"
        candidates.append({
            "id": f["id"],
            "name": f["name"],
            "kind": kind,
            "modifiedTime": f.get("modifiedTime"),
            "viewedByMeTime": f.get("viewedByMeTime"),
            "owners": [o.get("emailAddress") for o in f.get("owners", [])],
            "webViewLink": f.get("webViewLink"),
            "parents": [
                {"id": pid, "name": parent_cache.get(pid, "(unknown)")}
                for pid in (f.get("parents") or [])
            ],
            "excerpt": excerpts.get(f["id"]),
        })

    out = {
        "candidates": candidates,
        "stats": {
            "total": len(candidates),
            "with_excerpts": sum(1 for c in candidates if c["excerpt"]),
            "ranking_signal": ranking_signal,
        },
        "warnings": warnings,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
