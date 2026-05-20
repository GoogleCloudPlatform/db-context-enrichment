#!/usr/bin/env python3
"""Detect drift between a wiki's source_manifest.json and the sources on disk
(default mode) or on the live external systems (--live mode).

Five drift kinds:

  Local (always checked):
    CHANGED       — source path is in the manifest but its sha256 differs
                    from the current on-disk hash. Someone edited the local
                    copy.
    DELETED       — source path is in the manifest but the file no longer
                    exists on disk. Anything citing it is orphaned.
    NEW           — file exists under any sources/ directory but isn't in
                    the manifest. Probably a coverage opportunity.

  Live (only with --live):
    LIVE_CHANGED  — re-fetched live content differs from the on-disk
                    snapshot. The wiki has a stale picture of the source
                    (someone edited the doc, the schema changed, etc.).
    LIVE_DELETED  — live URI no longer resolves (404 / file deleted /
                    table dropped). The source is gone at the origin.

Severity is computed from claim impact. EXTRACTED claims carry verbatim
quotes, so any drift in a source they cite is HIGH (the quote may now be
wrong). INFERRED claims are MEDIUM. No-claim drift is LOW.

Outputs DRIFT.md (human-readable) + DRIFT.json (machine-readable, for the
Drift tab) at the wiki root.

Usage:
    # Local drift only (no GCP auth needed)
    python3 source_diff.py --wiki-root=path/to/customer

    # Local + live drift (needs the same GCP auth that built the wiki)
    python3 source_diff.py --wiki-root=path/to/customer --live

    # Acknowledged entries are filtered out of the next report
    python3 source_diff.py --wiki-root=... --acknowledged-file=.drift-acknowledged.json
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Make sibling scripts importable when run as a CLI from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acknowledge_drift import ACK_FILENAME  # noqa: E402

# Live-mode dependencies are conditional — we import only when --live is set,
# so the default code path stays import-free of GCP/google-api libs.
SOURCE_DIR_NAME = "sources"


@dataclass
class ClaimImpact:
    claim_id: str
    file: str           # narrative file the claim lives in
    tag: str            # EXTRACTED | INFERRED | AMBIGUOUS
    quote: str | None = None


@dataclass
class Drift:
    id: str
    kind: str           # changed | deleted | new | live_changed | live_deleted | live_failed
    severity: str       # high | medium | low
    source: str         # wiki-relative path
    manifest_hash: str | None
    current_hash: str | None
    size_change: int    # bytes (positive = grew, negative = shrunk)
    claims_impacted: list[ClaimImpact] = field(default_factory=list)
    explanation: str = ""
    suggested_action: str = ""
    # Live-mode extras (only populated when --live ran)
    live_check: str | None = None        # "fetched" | "skipped" | "failed"
    live_skip_reason: str | None = None
    explanation_extra: str = ""           # used by live_failed for the error msg
    fetcher: str | None = None            # which live fetcher matched


def hash_file(path: Path) -> tuple[str, int]:
    """Return (sha256, size_bytes) for path. Hashes the same way build_manifest
    does (sha256 of utf-8 text with replacement decoding)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        len(text),
    )


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"warning: {path} is not valid JSON: {e}", file=sys.stderr)
        return None


def collect_current_sources(wiki_root: Path) -> dict[str, tuple[str, int]]:
    """Walk wiki_root, hash every *.md under any sources/ directory (excluding
    the auto-generated sources/index.md). Returns {wiki_relative_path: (sha256, size)}."""
    out: dict[str, tuple[str, int]] = {}
    for src_dir in wiki_root.rglob(SOURCE_DIR_NAME):
        if not src_dir.is_dir():
            continue
        for p in sorted(src_dir.glob("*.md")):
            if p.name == "index.md":
                continue
            rel = p.relative_to(wiki_root).as_posix()
            out[rel] = hash_file(p)
    return out


def build_claim_map(
    wiki_root: Path, claims_index: dict | None,
) -> dict[str, list[ClaimImpact]]:
    """source_path -> [ClaimImpact, ...] (claims that cite this source).

    Walks every per-file claims.json sidecar listed in claims_index. Strips
    #anchor from source pointers so a single source path aggregates all
    claims regardless of which anchor they hit.
    """
    impacts: dict[str, list[ClaimImpact]] = defaultdict(list)
    if claims_index is None:
        return impacts
    for rel in claims_index.get("files_with_claims", []):
        sidecar = wiki_root / (rel + ".claims.json")
        sc = load_json(sidecar)
        if not sc:
            continue
        for claim in sc.get("claims", []):
            for src in claim.get("sources", []):
                src_path = src.split("#", 1)[0]
                impacts[src_path].append(ClaimImpact(
                    claim_id=claim.get("id", ""),
                    file=rel,
                    tag=claim.get("tag", ""),
                    quote=claim.get("quote"),
                ))
    return impacts


def severity_for(kind: str, claim_impacts: list[ClaimImpact]) -> str:
    """Severity rules:
      - changed / live_changed + any EXTRACTED claim → high (quote may be wrong)
      - changed / live_changed + any INFERRED claim  → medium
      - changed / live_changed + only AMBIGUOUS or none → low
      - deleted / live_deleted + any claim → high (orphaned citation)
      - deleted / live_deleted + no claim → low
      - new → low (it's an opportunity, not a regression)
      - live_failed → low (operational issue, not data drift)
    """
    bands = {ci.tag for ci in claim_impacts}
    if kind in ("deleted", "live_deleted"):
        return "high" if claim_impacts else "low"
    if kind == "new":
        return "low"
    if kind == "live_failed":
        return "low"
    # changed / live_changed
    if "EXTRACTED" in bands:
        return "high"
    if "INFERRED" in bands:
        return "medium"
    return "low"


def explain(d: Drift) -> str:
    """Short human explanation for the DRIFT.md row."""
    if d.kind == "changed":
        size_word = (
            f"+{d.size_change} bytes" if d.size_change > 0
            else f"{d.size_change} bytes" if d.size_change < 0
            else "size unchanged"
        )
        bands = {ci.tag for ci in d.claims_impacted}
        if d.claims_impacted:
            band_summary = ", ".join(sorted(bands))
            return (
                f"Hash differs from manifest ({size_word}); "
                f"{len(d.claims_impacted)} claim(s) cite this source "
                f"({band_summary})"
            )
        return f"Hash differs from manifest ({size_word}); no claims cite this source"
    if d.kind == "deleted":
        n = len(d.claims_impacted)
        if n == 0:
            return "Source file no longer exists; no claims cited it"
        return f"Source file no longer exists; {n} claim(s) cited it (now orphaned)"
    if d.kind == "new":
        return "Present on disk but not in manifest — source added since last build"
    if d.kind == "live_changed":
        bands = {ci.tag for ci in d.claims_impacted}
        if d.claims_impacted:
            band_summary = ", ".join(sorted(bands))
            return (
                f"Live source content differs from on-disk snapshot; "
                f"{len(d.claims_impacted)} claim(s) cite this source "
                f"({band_summary}). The wiki's snapshot of this source is stale."
            )
        return (
            "Live source content differs from on-disk snapshot; "
            "no claims cite this source"
        )
    if d.kind == "live_deleted":
        n = len(d.claims_impacted)
        if n == 0:
            return "Live source URI no longer resolves (404 / file deleted / table dropped)"
        return (
            f"Live source URI no longer resolves; {n} claim(s) cited it "
            f"(now orphaned at the origin)"
        )
    if d.kind == "live_failed":
        return f"Live re-fetch failed: {d.explanation_extra}"
    return ""


def suggest(d: Drift) -> str:
    if d.kind == "changed" and d.claims_impacted:
        files = sorted({ci.file for ci in d.claims_impacted})
        files_str = ", ".join(f"`{f}`" for f in files[:3]) + (
            f" (+{len(files)-3} more)" if len(files) > 3 else ""
        )
        return (
            f"Re-run `claims_sidecar.py` to verify EXTRACTED quotes still "
            f"validate; if any fail, regenerate the affected narrative "
            f"section: {files_str}"
        )
    if d.kind == "deleted":
        if d.claims_impacted:
            files = sorted({ci.file for ci in d.claims_impacted})
            return (
                f"Repoint the orphaned citation(s) in "
                f"{', '.join(f'`{f}`' for f in files[:3])} to a still-extant source, "
                f"or delete the citation if the underlying claim is no longer supportable."
            )
        return "Update the manifest by re-running `build_manifest.py`."
    if d.kind == "new":
        return (
            "Decide whether to cite this source from a narrative file "
            "(adds coverage) or leave it as standalone retrieval."
        )
    if d.kind == "live_changed":
        files = sorted({ci.file for ci in d.claims_impacted})
        if files:
            return (
                f"Re-capture the source via the warehouse / personal_context "
                f"agent so the on-disk snapshot is current; then re-run "
                f"`claims_sidecar.py` and regenerate any affected narrative: "
                f"{', '.join(f'`{f}`' for f in files[:3])}."
            )
        return (
            "Re-capture the source so the on-disk snapshot matches live; "
            "no narrative cites this source so claim impact is zero."
        )
    if d.kind == "live_deleted":
        return (
            "Source is gone at the origin. Decide whether to delete the "
            "on-disk snapshot (and any citations to it) or treat the snapshot "
            "as a historical record of a now-removed source."
        )
    if d.kind == "live_failed":
        return (
            "Operational issue, not data drift. Verify auth and try again "
            "(`gcloud auth list`, ADC, etc.). Acknowledge if this source "
            "is intentionally unavailable."
        )
    return ""


def make_drift_id(kind: str, source: str) -> str:
    h = hashlib.sha256(f"{kind}|{source}".encode("utf-8")).hexdigest()[:8]
    return f"drift-{kind[0].upper()}-{h}"


def _collapse_live_failed(drifts: list[Drift]) -> tuple[list[Drift], list[dict]]:
    """When several live_failed entries share the same root error (e.g. all
    say `[OTHER] command not found: 'bq'`), they're almost certainly a single
    operational issue — `bq` isn't installed, ADC isn't set up. Listing them
    individually buries the real signal in noise.

    Group live_failed entries by the leading `[KIND] <first-line>` prefix.
    For any group with >= 3 entries, drop the entries and emit a single
    "blanket banner" pseudo-entry the renderer can render once.

    Returns (kept_drifts, banners) where banners is [{kind_prefix, count,
    sample_explanation, sources}, ...].
    """
    grouped: dict[str, list[Drift]] = defaultdict(list)
    other: list[Drift] = []
    for d in drifts:
        if d.kind != "live_failed":
            other.append(d)
            continue
        # Group key: just the [KIND] tag and the first ~60 chars of the
        # explanation. Different doc IDs / table FQNs in the message body
        # would produce different keys, so we deliberately truncate.
        prefix = (d.explanation_extra or "")[:60]
        grouped[prefix].append(d)

    banners: list[dict] = []
    kept_failed: list[Drift] = []
    for key, entries in grouped.items():
        if len(entries) >= 3:
            banners.append({
                "key": key,
                "count": len(entries),
                "sample_explanation": entries[0].explanation_extra,
                "sources": [e.source for e in entries[:5]] + (
                    [f"... +{len(entries)-5} more"] if len(entries) > 5 else []
                ),
            })
        else:
            kept_failed.extend(entries)

    return other + kept_failed, banners


def detect_live(
    wiki_root: Path, manifest: dict, claim_impacts: dict[str, list[ClaimImpact]],
    *, max_workers: int = 4,
) -> tuple[list[Drift], dict[str, str]]:
    """Re-fetch each source from its origin and compare to the on-disk
    snapshot. Returns (drifts, skip_summary).

    Imports live_fetchers lazily so the default code path isn't gated on
    google-api-python-client / bq CLI being available.
    """
    try:
        from live_fetchers import (  # type: ignore
            dispatch, normalize_for_compare, extract_on_disk_body,
        )
    except ImportError:
        # When run via the skill installation, scripts dir is on sys.path
        # via the script's __file__; this branch handles odd PYTHONPATH cases.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from live_fetchers import (  # type: ignore
            dispatch, normalize_for_compare, extract_on_disk_body,
        )

    sources = manifest.get("sources", [])
    drifts: list[Drift] = []
    # Track (path -> reason) for sources we couldn't check — so the JSON
    # report can explain why some sources weren't live-checked.
    skips: dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(dispatch, s): s for s in sources}
        for fut in concurrent.futures.as_completed(futures):
            src = futures[fut]
            outcome = fut.result()
            path = outcome.source_path

            if outcome.skip_reason is not None:
                skips[path] = outcome.skip_reason
                continue

            on_disk_path = wiki_root / path
            if not on_disk_path.is_file():
                # Already covered by local DELETED detection — skip.
                continue

            if outcome.error is not None:
                if outcome.error.kind == "NOT_FOUND":
                    d = Drift(
                        id=make_drift_id("live_deleted", path),
                        kind="live_deleted",
                        severity="",
                        source=path,
                        manifest_hash=src.get("sha256"),
                        current_hash=None,
                        size_change=0,
                        claims_impacted=claim_impacts.get(path, []),
                        live_check="failed",
                        explanation_extra=str(outcome.error),
                    )
                else:
                    d = Drift(
                        id=make_drift_id(f"live_failed_{outcome.error.kind}", path),
                        kind="live_failed",
                        severity="",
                        source=path,
                        manifest_hash=src.get("sha256"),
                        current_hash=None,
                        size_change=0,
                        claims_impacted=claim_impacts.get(path, []),
                        live_check="failed",
                        explanation_extra=f"[{outcome.error.kind}] {outcome.error}",
                    )
                d.severity = severity_for(d.kind, d.claims_impacted)
                d.explanation = explain(d)
                d.suggested_action = suggest(d)
                drifts.append(d)
                continue

            # Successful fetch — compare normalized live vs. normalized on-disk gist body.
            assert outcome.snapshot is not None
            disk_text = on_disk_path.read_text(encoding="utf-8", errors="replace")
            disk_norm = normalize_for_compare(extract_on_disk_body(disk_text))
            live_norm = normalize_for_compare(outcome.snapshot.body)

            if disk_norm == live_norm:
                continue  # no live drift for this source

            # Compute a coarse "live size delta" — bytes between normalized forms.
            size_change = len(live_norm) - len(disk_norm)
            d = Drift(
                id=make_drift_id("live_changed", path),
                kind="live_changed",
                severity="",
                source=path,
                manifest_hash=src.get("sha256"),
                current_hash=None,
                size_change=size_change,
                claims_impacted=claim_impacts.get(path, []),
                live_check="fetched",
                fetcher=outcome.snapshot.fetcher,
            )
            d.severity = severity_for(d.kind, d.claims_impacted)
            d.explanation = explain(d)
            d.suggested_action = suggest(d)
            drifts.append(d)

    return drifts, skips


def detect(
    wiki_root: Path, manifest: dict, claim_impacts: dict[str, list[ClaimImpact]],
    *, acknowledged_ids: set[str],
) -> list[Drift]:
    current = collect_current_sources(wiki_root)
    manifest_sources = {s["path"]: s for s in manifest.get("sources", [])}

    drifts: list[Drift] = []

    # CHANGED + DELETED: walk the manifest, compare against current.
    for path, msrc in manifest_sources.items():
        manifest_hash = msrc.get("sha256")
        manifest_size = msrc.get("size", 0)
        if path not in current:
            d = Drift(
                id=make_drift_id("deleted", path),
                kind="deleted",
                severity="",
                source=path,
                manifest_hash=manifest_hash,
                current_hash=None,
                size_change=-manifest_size,
                claims_impacted=claim_impacts.get(path, []),
            )
            d.severity = severity_for(d.kind, d.claims_impacted)
            d.explanation = explain(d)
            d.suggested_action = suggest(d)
            drifts.append(d)
            continue
        cur_hash, cur_size = current[path]
        if cur_hash != manifest_hash:
            d = Drift(
                id=make_drift_id("changed", path),
                kind="changed",
                severity="",
                source=path,
                manifest_hash=manifest_hash,
                current_hash=cur_hash,
                size_change=cur_size - manifest_size,
                claims_impacted=claim_impacts.get(path, []),
            )
            d.severity = severity_for(d.kind, d.claims_impacted)
            d.explanation = explain(d)
            d.suggested_action = suggest(d)
            drifts.append(d)

    # NEW: in current but not in manifest.
    for path in current:
        if path not in manifest_sources:
            d = Drift(
                id=make_drift_id("new", path),
                kind="new",
                severity="",
                source=path,
                manifest_hash=None,
                current_hash=current[path][0],
                size_change=current[path][1],
                claims_impacted=claim_impacts.get(path, []),
            )
            d.severity = severity_for(d.kind, d.claims_impacted)
            d.explanation = explain(d)
            d.suggested_action = suggest(d)
            drifts.append(d)

    # Filter out acknowledged drifts.
    drifts = [d for d in drifts if d.id not in acknowledged_ids]

    # Sort: severity desc, then kind, then path.
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    drifts.sort(key=lambda d: (sev_rank.get(d.severity, 9), d.kind, d.source))
    return drifts


def severity_emoji(sev: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")


def render_md(
    drifts: list[Drift], wiki_root: Path, manifest: dict,
    *, live_skips: dict[str, str] | None = None, live_enabled: bool = False,
    live_banners: list[dict] | None = None,
) -> str:
    live_skips = live_skips or {}
    live_banners = live_banners or []
    by_kind: dict[str, list[Drift]] = defaultdict(list)
    for d in drifts:
        by_kind[d.kind].append(d)

    # Total live_failed for the header summary includes those collapsed
    # into banners — otherwise the header undercounts the operational issue.
    banner_failed = sum(b["count"] for b in live_banners)
    live_failed_count = len(by_kind.get("live_failed", [])) + banner_failed

    lines = [
        f"# Drift — {wiki_root.name}",
        "",
        f"_Generated by `source_diff.py` at "
        f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}_"
        + (" — `--live` enabled" if live_enabled else "") + ".",
        f"_Manifest built at: {manifest.get('built_at', 'unknown')}_",
        "",
        f"**{len(by_kind.get('changed', []))}** changed · "
        f"**{len(by_kind.get('deleted', []))}** deleted · "
        f"**{len(by_kind.get('new', []))}** new"
        + (
            f" · **{len(by_kind.get('live_changed', []))}** live-changed · "
            f"**{len(by_kind.get('live_deleted', []))}** live-deleted · "
            f"**{live_failed_count}** live-failed"
            if live_enabled else ""
        ),
        "",
    ]

    # Surface blanket-failure banners up top, before the per-entry sections.
    # Helpful when 13 of 13 live fetches failed because `bq` isn't installed
    # — listing them individually buries the real signal.
    for banner in live_banners:
        lines.append(
            f"> **🛑 {banner['count']} live fetch(es) failed with the same error.** "
            f"This is almost certainly a single operational issue, not "
            f"per-source data drift."
        )
        lines.append(">")
        lines.append(f"> **Error:** `{banner['sample_explanation']}`")
        lines.append(">")
        lines.append("> **Affected sources:** "
                     + ", ".join(f"`{s}`" for s in banner["sources"]))
        lines.append(">")
        lines.append(
            "> **Likely fixes:** install the missing CLI (`bq` / `gcloud`) "
            "or set up auth (`gcloud auth login`, "
            "`GOOGLE_APPLICATION_CREDENTIALS`). Re-run `source_diff.py "
            "--live` once fixed."
        )
        lines.append("")
    if not drifts and not live_skips:
        lines.append("_No drift detected — every source in the manifest still "
                     "matches its on-disk content, no extras have appeared._")
        lines.append("")
        return "\n".join(lines)

    for kind, label in (
        ("changed", "Changed sources (local)"),
        ("deleted", "Deleted sources (local)"),
        ("new", "New sources (local)"),
        ("live_changed", "Live-changed sources (the wiki snapshot is stale)"),
        ("live_deleted", "Live-deleted sources (gone at the origin)"),
        ("live_failed", "Live-fetch failures (operational, not data drift)"),
    ):
        items = by_kind.get(kind, [])
        if not items:
            continue
        lines.append(f"## {label}")
        lines.append("")
        for d in items:
            lines.append(f"### {d.id} — `{d.source}`")
            lines.append("")
            lines.append(f"- **Severity:** {d.severity} {severity_emoji(d.severity)}")
            lines.append(f"- **Kind:** {d.kind}")
            if d.fetcher:
                lines.append(f"- **Live fetcher:** `{d.fetcher}`")
            if d.kind not in ("new", "live_changed", "live_deleted", "live_failed"):
                lines.append(f"- **Manifest hash:** `{(d.manifest_hash or '?')[:12]}`")
            if d.kind == "changed":
                lines.append(f"- **Current hash:** `{(d.current_hash or '?')[:12]}`")
            if d.claims_impacted:
                bands = {ci.tag for ci in d.claims_impacted}
                files = sorted({ci.file for ci in d.claims_impacted})
                lines.append(
                    f"- **Claims impacted:** {len(d.claims_impacted)} "
                    f"({', '.join(sorted(bands))}) across "
                    f"{', '.join(f'`{f}`' for f in files[:3])}"
                    + (f" (+{len(files)-3} more)" if len(files) > 3 else "")
                )
            lines.append(f"- **Explanation:** {d.explanation}")
            lines.append(f"- **Suggested action:** {d.suggested_action}")
            lines.append("")

    if live_enabled and live_skips:
        lines.append("## Sources skipped (live mode)")
        lines.append("")
        lines.append(
            "_These sources weren't live-checked. Most are by-design "
            "volatile (drift would be expected) or don't have a live "
            "fetcher in this version._"
        )
        lines.append("")
        for path, reason in sorted(live_skips.items()):
            lines.append(f"- `{path}` — {reason}")
        lines.append("")
    return "\n".join(lines)


def render_json(
    drifts: list[Drift], wiki_root: Path, manifest: dict,
    *, live_skips: dict[str, str] | None = None, live_enabled: bool = False,
    live_banners: list[dict] | None = None,
) -> dict:
    live_skips = live_skips or {}
    live_banners = live_banners or []
    all_kinds = ("changed", "deleted", "new",
                 "live_changed", "live_deleted", "live_failed")
    return {
        "schema": "drift.v1",
        "wiki_root": wiki_root.name,
        "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_built_at": manifest.get("built_at"),
        "live_source_check": live_enabled,
        "drift_count": len(drifts),
        "by_severity": {
            sev: sum(1 for d in drifts if d.severity == sev)
            for sev in ("high", "medium", "low")
        },
        "by_kind": {
            kind: sum(1 for d in drifts if d.kind == kind)
            for kind in all_kinds
        },
        "drifts": [
            {
                **{k: v for k, v in asdict(d).items() if k != "claims_impacted"},
                "claims_impacted": [asdict(ci) for ci in d.claims_impacted],
            }
            for d in drifts
        ],
        "live_skips": [
            {"path": path, "reason": reason}
            for path, reason in sorted(live_skips.items())
        ],
        "live_banners": [
            {
                "count": b["count"],
                "sample_explanation": b["sample_explanation"],
                "sources": b["sources"],
            }
            for b in live_banners
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument(
        "--acknowledged-file",
        default=ACK_FILENAME,
        help="Path (relative to wiki root) to a JSON file listing acknowledged "
             "drift IDs. Acknowledged entries are dropped from the output. "
             f"Default: {ACK_FILENAME}",
    )
    ap.add_argument(
        "--baseline", default=None,
        help="Compare against a pinned snapshot (snapshots/<name>.json) "
             "instead of the current source_manifest.json. Useful for "
             "answering 'what's drifted since I pinned this baseline at "
             "QBR / release / audit time?'. Pin a baseline with "
             "build_manifest.py --snapshot=<name>.",
    )
    ap.add_argument(
        "--live", action="store_true",
        help="Also re-fetch each source from its origin (BigQuery / Drive) "
             "and compare to the on-disk snapshot. Adds live_changed / "
             "live_deleted / live_failed entries to the drift report. "
             "Requires the same GCP auth used to build the wiki originally.",
    )
    ap.add_argument(
        "--live-workers", type=int, default=4,
        help="Concurrency for --live fetches (default 4). Lower if you're "
             "hitting BigQuery/Drive rate limits.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    if args.baseline:
        baseline_path = wiki_root / "snapshots" / f"{args.baseline}.json"
        manifest = load_json(baseline_path)
        if manifest is None:
            available = []
            snap_dir = wiki_root / "snapshots"
            if snap_dir.is_dir():
                available = sorted(p.stem for p in snap_dir.glob("*.json"))
            hint = (
                f" Available snapshots in this wiki: {', '.join(available)}"
                if available else
                " No snapshots exist yet. Pin one with `build_manifest.py "
                "--snapshot=<name>`."
            )
            sys.exit(f"baseline snapshot not found: {baseline_path}.{hint}")
        if not args.quiet:
            print(
                f"using baseline snapshot: {args.baseline} "
                f"(pinned {manifest.get('snapshotted_at', '?')})",
                file=sys.stderr,
            )
    else:
        manifest = load_json(wiki_root / "source_manifest.json")
        if manifest is None:
            sys.exit(
                "source_manifest.json missing — run build_manifest.py first to "
                "establish the baseline."
            )
    claims_index = load_json(wiki_root / "claims_index.json")
    # claims_index can be None — drift detection still works, severity just
    # falls back to "low" for everything since no claim impact is computable.

    claim_impacts = build_claim_map(wiki_root, claims_index)

    ack_path = wiki_root / args.acknowledged_file
    ack_data = load_json(ack_path) or {}
    acknowledged_ids: set[str] = set(ack_data.get("acknowledged_ids", []))

    drifts = detect(
        wiki_root, manifest, claim_impacts,
        acknowledged_ids=acknowledged_ids,
    )

    live_skips: dict[str, str] = {}
    live_banners: list[dict] = []
    if args.live:
        if not args.quiet:
            print(
                f"--live: re-fetching {len(manifest.get('sources', []))} "
                f"source(s) (workers={args.live_workers})…",
                file=sys.stderr,
            )
        live_drifts, live_skips = detect_live(
            wiki_root, manifest, claim_impacts,
            max_workers=args.live_workers,
        )
        # Filter live drifts through the same acknowledgement set, then
        # collapse runs of identical live_failed entries into banners so a
        # blanket "bq not installed" or "auth failed for everything" doesn't
        # bury the real drift signal.
        live_drifts = [d for d in live_drifts if d.id not in acknowledged_ids]
        live_drifts, live_banners = _collapse_live_failed(live_drifts)
        drifts = sorted(
            drifts + live_drifts,
            key=lambda d: (
                {"high": 0, "medium": 1, "low": 2}.get(d.severity, 9),
                d.kind, d.source,
            ),
        )

    md_path = wiki_root / "DRIFT.md"
    json_path = wiki_root / "DRIFT.json"
    md_path.write_text(
        render_md(drifts, wiki_root, manifest, live_skips=live_skips,
                  live_enabled=args.live, live_banners=live_banners),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            render_json(drifts, wiki_root, manifest,
                        live_skips=live_skips, live_enabled=args.live,
                        live_banners=live_banners),
            indent=2, ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    if not args.quiet:
        by_kind = {k: sum(1 for d in drifts if d.kind == k)
                   for k in ("changed", "deleted", "new",
                             "live_changed", "live_deleted", "live_failed")}
        by_sev = {s: sum(1 for d in drifts if d.severity == s)
                  for s in ("high", "medium", "low")}
        # Mirror render_md's accounting: live_failed entries collapsed into
        # banners are dropped from `drifts` by _collapse_live_failed, so the
        # raw by_kind['live_failed'] count undercounts the operational issue.
        # Add banner counts back in so stderr matches DRIFT.md's header.
        banner_failed = sum(b["count"] for b in live_banners)
        msg = (
            f"drift: {by_kind['changed']} changed · "
            f"{by_kind['deleted']} deleted · {by_kind['new']} new"
        )
        if args.live:
            msg += (
                f" · {by_kind['live_changed']} live_changed · "
                f"{by_kind['live_deleted']} live_deleted · "
                f"{by_kind['live_failed'] + banner_failed} live_failed"
            )
        msg += (
            f" (severity: {by_sev['high']}H {by_sev['medium']}M {by_sev['low']}L) "
            f"→ {md_path.name}, {json_path.name}"
        )
        print(msg, file=sys.stderr)
    # Exit 1 if any HIGH-severity drift exists — useful for CI.
    high = sum(1 for d in drifts if d.severity == "high")
    return 0 if high == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
