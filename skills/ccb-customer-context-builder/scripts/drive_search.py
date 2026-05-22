#!/usr/bin/env python3
"""Search Google Drive for Docs / Sheets matching a folder or keyword.

Auth: Application Default Credentials. Run
    gcloud auth application-default login \\
      --scopes=https://www.googleapis.com/auth/drive.readonly,...
once before using this.

Output: JSON list of {id, name, mimeType, modifiedTime, webViewLink, owners}.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Iterator

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MIME = {
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "folder": "application/vnd.google-apps.folder",
}


def build_service():
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_in_folder(svc, folder_id: str, mime: str, recursive: bool) -> Iterator[dict]:
    stack = [folder_id]
    seen_folders: set[str] = set()
    while stack:
        fid = stack.pop()
        if fid in seen_folders:
            continue
        seen_folders.add(fid)
        page_token = None
        while True:
            resp = svc.files().list(
                q=f"'{fid}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, owners(emailAddress))",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for f in resp.get("files", []):
                if recursive and f["mimeType"] == MIME["folder"]:
                    stack.append(f["id"])
                if f["mimeType"] == MIME[mime]:
                    yield f
            page_token = resp.get("nextPageToken")
            if not page_token:
                break


def search_keyword(svc, query: str, mime: str) -> Iterator[dict]:
    # Drive's `fullText contains` does substring on title and body.
    # Multiple OR-joined terms => match any.
    terms = [t.strip() for t in query.split(" OR ") if t.strip()]
    full_text = " or ".join(f"fullText contains '{t}'" for t in terms)
    q = f"({full_text}) and mimeType='{MIME[mime]}' and trashed=false"
    page_token = None
    while True:
        resp = svc.files().list(
            q=q,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink, owners(emailAddress))",
            pageSize=200,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            orderBy="modifiedTime desc",
        ).execute()
        yield from resp.get("files", [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--folder-id", help="Drive folder ID to list")
    p.add_argument("--search", help="Keyword query (use ' OR ' between terms)")
    p.add_argument("--mime", choices=list(MIME), required=True)
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not args.folder_id and not args.search:
        p.error("must give --folder-id or --search")

    try:
        svc = build_service()
    except Exception as e:
        print(json.dumps({"error": f"auth failed: {e}"}), file=sys.stderr)
        sys.exit(2)

    try:
        if args.folder_id:
            it = list_in_folder(svc, args.folder_id, args.mime, args.recursive)
        else:
            it = search_keyword(svc, args.search, args.mime)
        results = []
        for f in it:
            results.append(f)
            if len(results) >= args.limit:
                break
    except HttpError as e:
        print(json.dumps({"error": f"drive api: {e}"}), file=sys.stderr)
        sys.exit(3)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for f in results:
            print(f"{f['id']}\t{f['modifiedTime']}\t{f['name']}")


if __name__ == "__main__":
    main()
