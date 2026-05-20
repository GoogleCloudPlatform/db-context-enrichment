#!/usr/bin/env python3
"""Extract a Google Doc as plain text with headings preserved.

Output JSON: {id, title, last_modified, owners, body}
where `body` is text with headings rendered as markdown (#, ##, ###).
"""
from __future__ import annotations

import argparse
import json
import sys

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


HEADING_PREFIX = {
    "TITLE": "# ",
    "SUBTITLE": "## ",
    "HEADING_1": "# ",
    "HEADING_2": "## ",
    "HEADING_3": "### ",
    "HEADING_4": "#### ",
    "HEADING_5": "##### ",
    "HEADING_6": "###### ",
}


def build_services():
    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/documents.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
    )
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


def render_paragraph(p: dict) -> str:
    style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
    prefix = HEADING_PREFIX.get(style, "")
    parts = []
    for el in p.get("elements", []):
        tr = el.get("textRun")
        if tr:
            parts.append(tr.get("content", ""))
    text = "".join(parts).rstrip("\n")
    if not text.strip():
        return ""
    return prefix + text


def extract_body(doc: dict, max_chars: int) -> str:
    out = []
    total = 0
    for el in doc.get("body", {}).get("content", []):
        p = el.get("paragraph")
        if not p:
            continue
        line = render_paragraph(p)
        if not line:
            continue
        out.append(line)
        total += len(line) + 1
        if total >= max_chars:
            out.append(f"\n[truncated at {max_chars} chars]")
            break
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--doc-id", required=True)
    p.add_argument("--max-chars", type=int, default=15000)
    args = p.parse_args()

    try:
        docs, drive = build_services()
    except Exception as e:
        print(json.dumps({"error": f"auth failed: {e}"}), file=sys.stderr)
        sys.exit(2)

    try:
        doc = docs.documents().get(documentId=args.doc_id).execute()
        meta = drive.files().get(
            fileId=args.doc_id,
            fields="id, name, modifiedTime, owners(emailAddress), webViewLink",
            supportsAllDrives=True,
        ).execute()
    except HttpError as e:
        print(json.dumps({"error": f"api: {e}"}), file=sys.stderr)
        sys.exit(3)

    out = {
        "id": meta["id"],
        "title": meta.get("name", doc.get("title", "")),
        "last_modified": meta.get("modifiedTime"),
        "owners": [o.get("emailAddress") for o in meta.get("owners", [])],
        "url": meta.get("webViewLink"),
        "body": extract_body(doc, args.max_chars),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
