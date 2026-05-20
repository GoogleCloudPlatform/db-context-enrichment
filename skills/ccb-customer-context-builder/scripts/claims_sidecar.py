#!/usr/bin/env python3
"""Parse claim-citation footnotes from a wiki tree and emit sidecar JSON.

Every narrative file (data_warehouse.md, internal_notes.md, lineage.md,
fields.md, index.md) embeds claim citations as Markdown footnotes:

    The fact_orders_daily table is partitioned by `order_date`.[^c1]

    [^c1]: EXTRACTED · `personal_context/sources/pipeline-design-doc.md#data-flow` · "Partitioned by `order_date`."

This script walks the wiki, extracts every `[^cN]` footnote and its
definition, validates the format, and writes a sidecar
`<file>.claims.json` next to each markdown file. It also writes a
roll-up `claims_index.json` at the wiki root listing every claim with
its file path + stable content-hash ID.

The on-disk markdown stays human-readable; the sidecar is what
gap_check.py, the critic, and the wiki-viewer side panel consume.

Usage:
    python3 claims_sidecar.py --wiki-root=path/to/customer
    python3 claims_sidecar.py --wiki-root=path/to/customer --report
    python3 claims_sidecar.py --wiki-root=path/to/customer --sample-extracted=10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VALID_TAGS = ("EXTRACTED", "INFERRED", "AMBIGUOUS")

# Files we never extract claims from — they're either source-of-truth gists
# or pure navigation.
SKIP_DIR_NAMES = ("sources",)

# Match a footnote reference in body text: [^c1], [^c42], [^c123].
FOOTNOTE_REF_RE = re.compile(r"\[\^c(\d+)\]")

# Match a footnote definition: [^c1]: TAG · `path#anchor` · "quote"
# We accept loose spacing; the parser splits on the first two `·` separators.
FOOTNOTE_DEF_RE = re.compile(
    r"^\s*\[\^c(\d+)\]:\s*(.+?)\s*$",
    re.MULTILINE,
)

# Slugify a gist title to its anchor (mirrors what GitHub Markdown does
# minus the trailing-number disambiguation).
_SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")


@dataclass
class Claim:
    id: str                    # stable: sha256(file_path + body + def)[:12]
    local_id: int              # the N in [^cN]; local to the file
    file: str                  # wiki-relative path
    tag: str                   # EXTRACTED | INFERRED | AMBIGUOUS
    sources: list[str] = field(default_factory=list)  # ["path#anchor", ...]
    quote: str | None = None   # the verbatim text for EXTRACTED
    raw: str = ""              # the raw footnote definition body
    line: int = 0              # 1-indexed line in the source markdown


@dataclass
class ParseError:
    file: str
    line: int
    local_id: int | None
    kind: str
    detail: str


def slugify_anchor(title: str) -> str:
    s = _SLUG_NONALNUM.sub("-", title.lower()).strip("-")
    return s or "section"


def collect_anchors(file_text: str) -> set[str]:
    """Return the set of anchor slugs declared in a file.

    Picks up both explicit anchors `## Title {#anchor-slug}` and the
    derived-from-title slug. The build hashes both so footnote pointers
    can use either form.
    """
    anchors: set[str] = set()
    for line in file_text.splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)(?:\s+\{#([a-z0-9\-]+)\})?\s*$", line)
        if not m:
            continue
        title, explicit = m.group(1), m.group(2)
        if explicit:
            anchors.add(explicit)
        # Strip the anchor decoration from title before slugifying
        title_clean = re.sub(r"\s*\{#[a-z0-9\-]+\}\s*$", "", title)
        anchors.add(slugify_anchor(title_clean))
    return anchors


def parse_footnote_definition(body: str) -> tuple[str, list[str], str | None, list[str]]:
    """Parse a footnote definition body. Returns (tag, sources, quote, errors).

    Body shape (· is the bullet separator U+00B7):
      EXTRACTED · `source-a.md#anchor` · "verbatim quote"
      INFERRED · derived from `source-a.md#anchor` + `source-b.md`
      AMBIGUOUS · `source-a.md#x` says X; `source-b.md#y` says Y

    Three positional, ·-separated fields:
      1. Tag (EXTRACTED | INFERRED | AMBIGUOUS)
      2. Source-pointer block — backticked path(s); may include prose
         ("derived from", "says X") around them
      3. Verbatim quote (EXTRACTED only) — last "..." substring

    The verbatim quote can itself contain backticks, so we ONLY scan field
    2 for source pointers — never field 3.
    """
    errors: list[str] = []
    parts = [p.strip() for p in body.split("·")]
    if len(parts) < 2:
        return "", [], None, [f"footnote body has fewer than 2 ·-separated parts: {body!r}"]
    tag_part = parts[0].strip().upper()
    if tag_part not in VALID_TAGS:
        errors.append(f"unknown tag {tag_part!r} (expected one of {VALID_TAGS})")
        return tag_part, [], None, errors

    # Sources live ONLY in field 2 (parts[1]). Field 3+ is the verbatim quote
    # for EXTRACTED, and that quote can contain backticks of its own. AMBIGUOUS
    # bodies often contain non-source code spans too (regex patterns, table
    # names quoted from the conflicting sources) — so we filter to backticked
    # things that LOOK like source pointers: must contain '/' (a directory
    # separator) OR end in '.md' (a file extension). This rejects bare
    # identifiers like `attribution_summary_vN` while still accepting
    # `sources/bq_show_schema.md` and `pipeline-design-doc-q1-2026.md#anchor`.
    source_block = parts[1] if len(parts) > 1 else ""
    raw_backticks = re.findall(r"`([^`]+)`", source_block)
    sources = [b for b in raw_backticks if "/" in b or b.endswith(".md") or "#" in b]
    if not sources:
        errors.append(
            "no backticked source pointer found in footnote field 2 "
            "(must contain '/' or end in '.md')"
        )

    quote: str | None = None
    if tag_part == "EXTRACTED":
        # Quote lives in field 3+. Re-join parts[2:] in case the quote itself
        # contained a · (rare; survives the round-trip).
        quote_block = " · ".join(parts[2:]) if len(parts) > 2 else ""
        qm = list(re.finditer(r'"([^"]*)"', quote_block))
        if qm:
            quote = qm[-1].group(1)
        else:
            errors.append("EXTRACTED footnote has no quoted verbatim string in field 3")

    return tag_part, sources, quote, errors


def parse_file(file_path: Path, wiki_root: Path) -> tuple[list[Claim], list[ParseError]]:
    """Extract every claim from one markdown file.

    Returns (claims, errors). Files under any */sources/ directory return
    empty lists — they're source-of-truth and don't carry citations.
    """
    rel = file_path.relative_to(wiki_root).as_posix()
    if any(part in SKIP_DIR_NAMES for part in file_path.relative_to(wiki_root).parts[:-1]):
        return [], []

    text = file_path.read_text(encoding="utf-8", errors="replace")

    # Track each footnote def with its line number for better error reporting.
    def_lines: dict[int, tuple[int, str]] = {}
    for line_idx, line in enumerate(text.splitlines(), start=1):
        m = re.match(r"^\s*\[\^c(\d+)\]:\s*(.+?)\s*$", line)
        if m:
            local_id = int(m.group(1))
            def_lines[local_id] = (line_idx, m.group(2))

    # Find every footnote reference in body (first occurrence wins for line).
    ref_lines: dict[int, int] = {}
    for line_idx, line in enumerate(text.splitlines(), start=1):
        for m in FOOTNOTE_REF_RE.finditer(line):
            local_id = int(m.group(1))
            ref_lines.setdefault(local_id, line_idx)

    claims: list[Claim] = []
    errors: list[ParseError] = []

    # Every reference needs a definition.
    for local_id, ref_line in ref_lines.items():
        if local_id not in def_lines:
            errors.append(ParseError(
                file=rel, line=ref_line, local_id=local_id,
                kind="missing_definition",
                detail=f"[^c{local_id}] referenced at line {ref_line} but no [^c{local_id}]: definition found",
            ))

    # Every definition needs a reference.
    for local_id, (def_line, body) in def_lines.items():
        if local_id not in ref_lines:
            errors.append(ParseError(
                file=rel, line=def_line, local_id=local_id,
                kind="orphan_definition",
                detail=f"[^c{local_id}]: defined at line {def_line} but never referenced in body",
            ))
            continue
        tag, sources, quote, parse_errs = parse_footnote_definition(body)
        for pe in parse_errs:
            errors.append(ParseError(
                file=rel, line=def_line, local_id=local_id,
                kind="malformed_definition",
                detail=pe,
            ))
        if not tag or tag not in VALID_TAGS:
            continue
        # Stable ID: hash file + body + the referencing line context.
        h = hashlib.sha256(
            f"{rel}|{local_id}|{body}".encode("utf-8")
        ).hexdigest()[:12]
        claims.append(Claim(
            id=h, local_id=local_id, file=rel,
            tag=tag, sources=sources, quote=quote,
            raw=body, line=ref_lines[local_id],
        ))
    claims.sort(key=lambda c: c.local_id)
    return claims, errors


def resolve_source_pointer(
    pointer: str, wiki_root: Path,
) -> tuple[Path | None, str | None, str | None]:
    """Split a `path#anchor` pointer; return (resolved path, anchor, error)."""
    if "#" in pointer:
        path_part, anchor = pointer.split("#", 1)
    else:
        path_part, anchor = pointer, None
    candidate = (wiki_root / path_part).resolve()
    try:
        candidate.relative_to(wiki_root.resolve())
    except ValueError:
        return None, anchor, f"pointer escapes wiki root: {pointer}"
    if not candidate.is_file():
        return None, anchor, f"pointer file not found: {path_part}"
    return candidate, anchor, None


def validate_claims(
    claims: list[Claim], wiki_root: Path, *, sample_extracted: int = 0,
) -> list[ParseError]:
    """Cross-file validation: pointed-at sources must exist, anchors must
    resolve, and EXTRACTED quotes must literal-substring-match the gist."""
    errors: list[ParseError] = []
    extracted_seen = 0
    for claim in claims:
        for src in claim.sources:
            path, anchor, err = resolve_source_pointer(src, wiki_root)
            if err:
                errors.append(ParseError(
                    file=claim.file, line=claim.line, local_id=claim.local_id,
                    kind="dangling_source",
                    detail=err,
                ))
                continue
            if anchor:
                src_text = path.read_text(encoding="utf-8", errors="replace")
                anchors = collect_anchors(src_text)
                if anchor not in anchors:
                    errors.append(ParseError(
                        file=claim.file, line=claim.line, local_id=claim.local_id,
                        kind="missing_anchor",
                        detail=f"anchor #{anchor} not found in {src}",
                    ))
            # EXTRACTED literal-substring check, sampled
            if (
                claim.tag == "EXTRACTED" and claim.quote
                and (sample_extracted == 0 or extracted_seen < sample_extracted)
            ):
                extracted_seen += 1
                src_text = path.read_text(encoding="utf-8", errors="replace") \
                    if path.is_file() else ""
                # Normalize: strip leading blockquote markers ("> "), collapse
                # whitespace runs, lowercase. The quote in the citation is
                # typically a single line, while the source has it as a multi-line
                # blockquote — without these strips the substring won't match.
                src_no_bq = re.sub(r"^\s*>\s?", "", src_text, flags=re.MULTILINE)
                norm_src = re.sub(r"\s+", " ", src_no_bq).lower()
                norm_quote = re.sub(r"\s+", " ", claim.quote).lower()
                if norm_quote and norm_quote not in norm_src:
                    errors.append(ParseError(
                        file=claim.file, line=claim.line, local_id=claim.local_id,
                        kind="extracted_mismatch",
                        detail=f"verbatim quote not found in {src}: {claim.quote[:80]!r}",
                    ))
    return errors


def find_narrative_files(wiki_root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(wiki_root.rglob("*.md")):
        # Skip files under any sources/ subdir.
        rel_parts = p.relative_to(wiki_root).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        out.append(p)
    return out


def write_sidecars(
    wiki_root: Path, claims_by_file: dict[str, list[Claim]],
) -> None:
    for rel, claims in claims_by_file.items():
        sidecar = wiki_root / (rel + ".claims.json")
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "claims.v1",
            "file": rel,
            "claim_count": len(claims),
            "by_band": {
                band: sum(1 for c in claims if c.tag == band)
                for band in VALID_TAGS
            },
            "claims": [asdict(c) for c in claims],
        }
        sidecar.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def write_index(wiki_root: Path, all_claims: list[Claim], errors: list[ParseError]) -> Path:
    payload = {
        "schema": "claims_index.v1",
        "wiki_root": wiki_root.name,
        "claim_count": len(all_claims),
        "by_band": {
            band: sum(1 for c in all_claims if c.tag == band)
            for band in VALID_TAGS
        },
        "files_with_claims": sorted({c.file for c in all_claims}),
        "errors": [asdict(e) for e in errors],
    }
    out_path = wiki_root / "claims_index.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True,
                    help="Customer wiki root (e.g. .../wikis/<customer>/).")
    ap.add_argument("--report", action="store_true",
                    help="Print a human-readable summary to stderr.")
    ap.add_argument("--sample-extracted", type=int, default=10,
                    help="Sample N EXTRACTED claims for verbatim-substring "
                         "verification (0 = all). Default 10.")
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress non-error output.")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    md_files = find_narrative_files(wiki_root)
    claims_by_file: dict[str, list[Claim]] = {}
    all_claims: list[Claim] = []
    all_errors: list[ParseError] = []

    for md in md_files:
        claims, errs = parse_file(md, wiki_root)
        rel = md.relative_to(wiki_root).as_posix()
        # Always write a sidecar (even if empty) so the dep graph can rely on
        # one-per-file. Skip files with no claims AND no errors? No — empty
        # sidecar is a valid signal that the file has been processed.
        claims_by_file[rel] = claims
        all_claims.extend(claims)
        all_errors.extend(errs)

    # Cross-file validation
    all_errors.extend(validate_claims(
        all_claims, wiki_root, sample_extracted=args.sample_extracted,
    ))

    write_sidecars(wiki_root, claims_by_file)
    index_path = write_index(wiki_root, all_claims, all_errors)

    if not args.quiet:
        print(
            f"claims: {len(all_claims)} across {len(claims_by_file)} files; "
            f"errors: {len(all_errors)}; index: {index_path.name}",
            file=sys.stderr,
        )
    if args.report:
        bands = {b: sum(1 for c in all_claims if c.tag == b) for b in VALID_TAGS}
        print("Band counts:", file=sys.stderr)
        for b in VALID_TAGS:
            print(f"  {b:10} {bands[b]}", file=sys.stderr)
        if all_errors:
            print(f"\nErrors ({len(all_errors)}):", file=sys.stderr)
            for e in all_errors[:50]:
                print(f"  [{e.kind}] {e.file}:{e.line} {e.detail}",
                      file=sys.stderr)
            if len(all_errors) > 50:
                print(f"  ... {len(all_errors) - 50} more", file=sys.stderr)

    # Exit non-zero if HIGH-severity errors (extracted mismatch, dangling
    # source) were found — useful in CI but the critic surfaces them too.
    high_kinds = {"extracted_mismatch", "dangling_source", "missing_definition"}
    high_count = sum(1 for e in all_errors if e.kind in high_kinds)
    return 0 if high_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
