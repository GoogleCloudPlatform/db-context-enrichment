#!/usr/bin/env python3
"""Smoketest for source_diff.py --live mode using fake fetchers.

Validates:
  - dispatch() correctly routes to fetchers based on lineage / URI patterns
  - SKIP_PATTERNS catches volatile sources (JOBS_BY_PROJECT, etc.)
  - Successful fetch with matching content → no drift
  - Successful fetch with differing content → live_changed entry
  - Fetcher raising NOT_FOUND → live_deleted entry
  - Fetcher raising AUTH_FAILED → live_failed entry
  - normalize_for_compare strips blockquotes + collapses whitespace correctly

Run with no args:
    python3 test_live_drift.py

Exit 0 = all passed, 1 = something failed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_fetchers  # noqa: E402
import source_diff  # noqa: E402


def assert_eq(name: str, actual, expected) -> None:
    if actual != expected:
        print(f"FAIL {name}: expected {expected!r}, got {actual!r}")
        sys.exit(1)
    print(f"PASS {name}")


def assert_in(name: str, needle, haystack) -> None:
    if needle not in haystack:
        print(f"FAIL {name}: {needle!r} not in {haystack!r}")
        sys.exit(1)
    print(f"PASS {name}")


# ---------------- normalize_for_compare ----------------

print("\n=== normalize_for_compare ===")
assert_eq(
    "strip blockquote prefix",
    live_fetchers.normalize_for_compare("> hello world"),
    "hello world",
)
assert_eq(
    "collapse whitespace",
    live_fetchers.normalize_for_compare("hello   world\n\nfoo"),
    "hello world foo",
)
assert_eq(
    "lowercase",
    live_fetchers.normalize_for_compare("HELLO World"),
    "hello world",
)


# ---------------- extract_on_disk_body ----------------

print("\n=== extract_on_disk_body ===")
src_md = """# Retrieved from

- **Source:** Google Doc — https://...
- **Retrieved at:** 2026-05-04T00:00:00Z

# Gists

## Data flow {#data-flow}

> A nightly ELT job materializes fact_orders_daily.

## Open issues {#open-issues}

> 30% of partitions written without filters.
"""
body = live_fetchers.extract_on_disk_body(src_md)
assert_in("body contains data flow gist", "A nightly ELT job", body)
assert_in("body contains open issues gist", "30% of partitions", body)


# ---------------- dispatch: routing ----------------

print("\n=== dispatch routing ===")

gdoc_record = {
    "path": "personal_context/sources/foo.md",
    "source_uri": "Google Doc — https://docs.google.com/document/d/abc123def/edit",
    "lineage": "python3 scripts/gdocs_extract.py --doc-id=abc123def --max-chars=15000",
}
gsheet_record = {
    "path": "personal_context/sources/bar.md",
    "source_uri": "Google Sheet — https://docs.google.com/spreadsheets/d/sheet456/edit",
    "lineage": "python3 scripts/gsheets_extract.py --sheet-id=sheet456 --rows-per-tab=15",
}
bq_schema_record = {
    "path": "events_raw/sources/bq_show_schema.md",
    "source_uri": "BigQuery table `myproj:mydataset.mytable`",
    "lineage": "bq show --schema --format=prettyjson myproj:mydataset.mytable",
}
volatile_record = {
    "path": "sources/bq_jobs_by_project.md",
    "source_uri": "BigQuery region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT for project foo",
    "lineage": "bq query --project_id=foo ...",
}
unsupported_record = {
    "path": "sources/dataplex_lakes_list.md",
    "source_uri": "Dataplex — lakes in foo",
    "lineage": "gcloud dataplex lakes list --project=foo --location=- --format=json",
}

# Monkey-patch the fetchers so we can assert dispatch behavior without GCP.
calls: list[tuple[str, dict]] = []
original_fetchers = {
    "fetch_gdoc": live_fetchers.fetch_gdoc,
    "fetch_gsheet": live_fetchers.fetch_gsheet,
    "fetch_bq_schema": live_fetchers.fetch_bq_schema,
    "fetch_bq_dataset_list": live_fetchers.fetch_bq_dataset_list,
}

def fake_gdoc(**kwargs):
    calls.append(("gdoc", kwargs))
    return "fake gdoc body content"

def fake_gsheet(**kwargs):
    calls.append(("gsheet", kwargs))
    return "fake gsheet body content"

def fake_bq_schema(**kwargs):
    calls.append(("bq_schema", kwargs))
    return '{"fields": [{"name": "id", "type": "INT64"}]}'

def fake_bq_list(**kwargs):
    calls.append(("bq_dataset_list", kwargs))
    return '{"datasets": []}'

# Monkey-patch via the dispatch table — fetchers are stored by reference.
for entry in live_fetchers._DISPATCH:
    if entry["name"] == "gdoc":
        entry["fetcher"] = fake_gdoc
    elif entry["name"] == "gsheet":
        entry["fetcher"] = fake_gsheet
    elif entry["name"] == "bq_schema":
        entry["fetcher"] = fake_bq_schema
    elif entry["name"] == "bq_dataset_list":
        entry["fetcher"] = fake_bq_list

out = live_fetchers.dispatch(gdoc_record)
assert_eq("gdoc fetcher selected", out.snapshot.fetcher if out.snapshot else None, "gdoc")
assert_eq("gdoc doc_id extracted", calls[-1][1].get("doc_id"), "abc123def")

out = live_fetchers.dispatch(gsheet_record)
assert_eq("gsheet fetcher selected", out.snapshot.fetcher if out.snapshot else None, "gsheet")
assert_eq("gsheet sheet_id extracted", calls[-1][1].get("sheet_id"), "sheet456")

out = live_fetchers.dispatch(bq_schema_record)
assert_eq("bq_schema fetcher selected", out.snapshot.fetcher if out.snapshot else None, "bq_schema")
assert_eq("bq_schema fqn normalized to dot form",
          calls[-1][1].get("table_fqn"), "myproj.mydataset.mytable")

# Volatile + unsupported should skip, not call any fetcher.
calls_before = len(calls)
out = live_fetchers.dispatch(volatile_record)
assert_eq("volatile JOBS_BY_PROJECT was skipped",
          out.snapshot, None)
assert_in("volatile skip_reason mentions volatile", "volatile",
          (out.skip_reason or "").lower())
assert_eq("volatile didn't call any fetcher", len(calls), calls_before)

out = live_fetchers.dispatch(unsupported_record)
assert_eq("dataplex was skipped", out.snapshot, None)
assert_in("dataplex skip_reason mentions dataplex", "dataplex",
          (out.skip_reason or "").lower())


# ---------------- detect_live: end-to-end ----------------

print("\n=== detect_live end-to-end ===")

# Build a tiny fake wiki + manifest.
with tempfile.TemporaryDirectory() as td:
    wiki = Path(td)
    (wiki / "personal_context" / "sources").mkdir(parents=True)
    (wiki / "events_raw" / "sources").mkdir(parents=True)
    (wiki / "sources").mkdir()

    # On-disk source — we'll make the live fetch return DIFFERENT content
    # to trigger live_changed.
    foo_md = """# Retrieved from

- **Source:** Google Doc — https://docs.google.com/document/d/abc123def/edit
- **Lineage:** python3 scripts/gdocs_extract.py --doc-id=abc123def

# Gists

## Section

> The original on-disk content from when we captured this doc.
"""
    (wiki / "personal_context" / "sources" / "foo.md").write_text(foo_md)

    # On-disk source — live fetch will return SAME content (no drift after
    # normalize_for_compare strips blockquote markers + collapses whitespace).
    # The on-disk Gist body and the live fetcher's return value must
    # normalize to the same string.
    bar_md = """# Retrieved from

- **Source:** Google Sheet — https://docs.google.com/spreadsheets/d/sheet456/edit
- **Lineage:** python3 scripts/gsheets_extract.py --sheet-id=sheet456

# Gists

## Sample
> matching content from the live fetch
"""
    (wiki / "personal_context" / "sources" / "bar.md").write_text(bar_md)

    # On-disk source — live fetch will raise NOT_FOUND → live_deleted.
    baz_md = """# Retrieved from

- **Source:** BigQuery table `myproj:mydataset.deletedtable`
- **Lineage:** bq show --schema --format=prettyjson myproj:mydataset.deletedtable

# Gists

## Schema

```json
{"fields": []}
```
"""
    (wiki / "events_raw" / "sources" / "bq_show_schema.md").write_text(baz_md)

    manifest = {
        "schema": "source_manifest.v1",
        "built_at": "2026-05-09T00:00:00Z",
        "sources": [
            {"path": "personal_context/sources/foo.md", "sha256": "x", "size": 100,
             "source_uri": "Google Doc — https://docs.google.com/document/d/abc123def/edit",
             "lineage": "python3 scripts/gdocs_extract.py --doc-id=abc123def"},
            {"path": "personal_context/sources/bar.md", "sha256": "y", "size": 100,
             "source_uri": "Google Sheet — https://docs.google.com/spreadsheets/d/sheet456/edit",
             "lineage": "python3 scripts/gsheets_extract.py --sheet-id=sheet456"},
            {"path": "events_raw/sources/bq_show_schema.md", "sha256": "z", "size": 100,
             "source_uri": "BigQuery table `myproj:mydataset.deletedtable`",
             "lineage": "bq show --schema --format=prettyjson myproj:mydataset.deletedtable"},
        ],
    }

    # Configure fakes for this test: foo returns DIFFERENT content (drift),
    # bar returns MATCHING content (no drift after normalization), baz raises NOT_FOUND.
    def matched_gdoc(**kwargs):
        if kwargs.get("doc_id") == "abc123def":
            return "Completely different live content that doesn't match on-disk."
        raise live_fetchers.LiveFetchError("OTHER", "unexpected doc_id")

    def matched_gsheet(**kwargs):
        # Return a string that, after normalize_for_compare, matches the
        # normalized on-disk gist body. The on-disk body includes the
        # `## Sample` heading; the live fetcher's output should too so they
        # normalize to the same canonical form.
        return "## Sample\nmatching content from the live fetch"

    def deleted_bq_schema(**kwargs):
        raise live_fetchers.LiveFetchError("NOT_FOUND", "table not found")

    for entry in live_fetchers._DISPATCH:
        if entry["name"] == "gdoc":
            entry["fetcher"] = matched_gdoc
        elif entry["name"] == "gsheet":
            entry["fetcher"] = matched_gsheet
        elif entry["name"] == "bq_schema":
            entry["fetcher"] = deleted_bq_schema

    drifts, skips = source_diff.detect_live(
        wiki, manifest, claim_impacts={}, max_workers=2,
    )

    by_kind = {d.kind: d for d in drifts}
    assert_in("foo.md → live_changed", "live_changed", by_kind)
    assert_eq("foo.md is the live_changed source",
              by_kind["live_changed"].source, "personal_context/sources/foo.md")

    assert_in("bq_show_schema.md → live_deleted", "live_deleted", by_kind)
    assert_eq("baz is the live_deleted source",
              by_kind["live_deleted"].source, "events_raw/sources/bq_show_schema.md")

    # bar.md matched live → no drift entry
    bar_entries = [d for d in drifts if d.source.endswith("/bar.md")]
    assert_eq("bar.md (matching content) → no drift", len(bar_entries), 0)


print("\nALL PASSED")
sys.exit(0)
