#!/usr/bin/env python3
"""Extract metadata + a row sample from a Google Sheet.

Output JSON: {id, title, last_modified, owners, tabs: [{title, row_count,
col_count, header, sample_rows}]}
"""
from __future__ import annotations

import argparse
import json
import sys

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def build_services():
    creds, _ = google.auth.default(
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
    )
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return sheets, drive


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sheet-id", required=True)
    p.add_argument("--rows-per-tab", type=int, default=15)
    args = p.parse_args()

    try:
        sheets, drive = build_services()
    except Exception as e:
        print(json.dumps({"error": f"auth failed: {e}"}), file=sys.stderr)
        sys.exit(2)

    try:
        meta = drive.files().get(
            fileId=args.sheet_id,
            fields="id, name, modifiedTime, owners(emailAddress), webViewLink",
            supportsAllDrives=True,
        ).execute()
        ss = sheets.spreadsheets().get(
            spreadsheetId=args.sheet_id,
            includeGridData=False,
        ).execute()
    except HttpError as e:
        print(json.dumps({"error": f"api: {e}"}), file=sys.stderr)
        sys.exit(3)

    tabs = []
    for s in ss.get("sheets", []):
        props = s.get("properties", {})
        title = props.get("title", "")
        grid = props.get("gridProperties", {})
        row_count = grid.get("rowCount", 0)
        col_count = grid.get("columnCount", 0)

        end_row = min(row_count, args.rows_per_tab + 1)  # +1 for header
        if end_row < 2:
            tabs.append({
                "title": title,
                "row_count": row_count,
                "col_count": col_count,
                "header": [],
                "sample_rows": [],
            })
            continue
        rng = f"'{title}'!A1:{_col_letter(col_count)}{end_row}"
        try:
            values = sheets.spreadsheets().values().get(
                spreadsheetId=args.sheet_id, range=rng,
            ).execute().get("values", [])
        except HttpError:
            values = []
        header = values[0] if values else []
        sample = values[1:] if len(values) > 1 else []
        tabs.append({
            "title": title,
            "row_count": row_count,
            "col_count": col_count,
            "header": header,
            "sample_rows": sample,
        })

    out = {
        "id": meta["id"],
        "title": meta.get("name"),
        "last_modified": meta.get("modifiedTime"),
        "owners": [o.get("emailAddress") for o in meta.get("owners", [])],
        "url": meta.get("webViewLink"),
        "tabs": tabs,
    }
    print(json.dumps(out, indent=2))


def _col_letter(n: int) -> str:
    """1 -> A, 27 -> AA, etc."""
    n = max(1, min(n, 18278))
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


if __name__ == "__main__":
    main()
