#!/usr/bin/env python3
"""Re-validate drift entries after the cheap hash-based detection flagged
them as CHANGED.

source_diff.py's stage 1 is sha256 inequality — fast, deterministic,
but full of false positives (cosmetic edits like adding a trailing
newline trip the same severity rule as a real semantic change). This
script is stage 2: for each CHANGED entry, walk the claims that cite
the source and check whether each claim is STILL SUPPORTED by the new
content:

  - EXTRACTED claim: literal-substring check of the verbatim quote
                     against the new content (normalized).
                     Survives → claim unaffected.
  - INFERRED claim:  anchor existence check. If the cited #anchor
                     still resolves to a section in the new content,
                     the claim is assumed still supportable. Survives.
                     (Cheap proxy; --llm escalates this to a real
                     semantic check.)
  - AMBIGUOUS claim: always drops (signal too weak to be impactful).

After re-validation, severity is recomputed from the SURVIVING claims:

  any EXTRACTED still impacts → high
  any INFERRED still impacts  → medium
  only AMBIGUOUS or none      → low

Often this DOWNGRADES the original severity — a CHANGED source that
HIGH-flagged because it had EXTRACTED citations is downgraded to MEDIUM
or LOW once we confirm the verbatim quotes still validate.

Optional `--llm` adds stage 3 for INFERRED claims that pass the cheap
check: ask Claude whether the claim is still supported by the new
content. Costs API tokens; off by default; uses the user's existing
Claude Code auth via `claude -p`.

Outputs are written back into DRIFT.json + DRIFT.md with new fields:
  severity_original              the band stage 1 assigned
  severity_after_revalidation    the band after surviving claims
  revalidated_at                 ISO timestamp
  revalidation_summary           "8/12 EXTRACTED quotes still validate"
  revalidation_per_claim         per-claim {claim_id, tag, status, ...}

Usage:
    python3 revalidate_drift.py --wiki-root=path/to/customer
    python3 revalidate_drift.py --wiki-root=... --llm   # stage 3 too
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Normalization mirrors live_fetchers.normalize_for_compare so EXTRACTED
# substring checks survive trivial blockquote/whitespace differences.
_BLOCKQUOTE_PREFIX = re.compile(r"^\s*>\s?", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "section"


def normalize(text: str) -> str:
    s = _BLOCKQUOTE_PREFIX.sub("", text)
    s = _WHITESPACE.sub(" ", s)
    return s.strip().lower()


def collect_anchors_and_sections(text: str) -> dict[str, str]:
    """Return {anchor_slug: text_under_this_heading}.

    Anchors come from explicit `{#kebab-slug}` decorations OR are derived
    from heading titles. The section text is everything from the heading
    line until the next heading of equal-or-greater rank.
    """
    out: dict[str, str] = {}
    lines = text.splitlines()
    # Walk to find headings + their text spans.
    heading_positions: list[tuple[int, int, str, str | None]] = []  # (line_idx, level, title, explicit_anchor)
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+?)(?:\s+\{#([a-z0-9\-]+)\})?\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        explicit = m.group(3)
        heading_positions.append((i, level, title, explicit))
    for idx, (line_i, level, title, explicit) in enumerate(heading_positions):
        # Find the end of this section: next heading of level <= this one.
        end_i = len(lines)
        for next_i, next_level, _, _ in heading_positions[idx + 1:]:
            if next_level <= level:
                end_i = next_i
                break
        section_body = "\n".join(lines[line_i + 1:end_i]).strip()
        for anchor in [explicit, _slug(title)]:
            if anchor and anchor not in out:
                out[anchor] = section_body
    return out


def load_json(p: Path) -> dict | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_claims_for_file(wiki_root: Path, narrative_file: str) -> list[dict]:
    """Load the claims sidecar for one narrative file."""
    sidecar = wiki_root / (narrative_file + ".claims.json")
    sc = load_json(sidecar)
    return sc.get("claims", []) if sc else []


def revalidate_extracted(claim: dict, new_source_text: str) -> tuple[str, str]:
    """Returns (status, detail).

    status: "pass" (quote still matches), "fail" (quote not found),
            "no_quote" (claim was EXTRACTED but no quote in def — shouldn't happen).
    """
    quote = claim.get("quote")
    if not quote:
        return ("no_quote", "EXTRACTED claim has no quote field")
    norm_src = normalize(new_source_text)
    norm_quote = normalize(quote)
    if norm_quote and norm_quote in norm_src:
        return ("pass", "verbatim quote still present in new content")
    return ("fail", f"verbatim quote not found in new content: {quote[:80]!r}")


def revalidate_inferred_cheap(
    claim: dict, new_source_text: str, anchors: dict[str, str],
) -> tuple[str, str]:
    """Cheap INFERRED check: does the cited #anchor still exist?

    Returns (status, detail).

    status:
      "pass"      anchor exists in new content — claim still supportable
      "fail"      anchor doesn't exist — claim is orphaned
      "no_source" claim has no source pointer
    """
    # Look at the first source pointer. INFERRED can have multiple sources;
    # we re-check against the first one (canonical citation).
    sources = claim.get("sources") or []
    if not sources:
        return ("no_source", "INFERRED claim has no source pointer")
    src = sources[0]
    if "#" not in src:
        # No anchor — claim cites the file as a whole. Pass if file
        # is non-empty.
        return ("pass" if new_source_text.strip() else "fail",
                "no #anchor in citation; checked file is non-empty")
    _, anchor = src.split("#", 1)
    if anchor not in anchors:
        return ("fail", f"anchor #{anchor} no longer resolves in new content")
    # Cheap "is the section materially the same as expected" check we
    # can't really do without the OLD content. We DO have the section
    # text; absent prior content, just confirm the section is non-empty.
    section = anchors[anchor]
    if not section.strip():
        return ("fail", f"anchor #{anchor} resolves but section is empty")
    return ("pass", f"anchor #{anchor} still resolves with non-empty content")


def _claude_env() -> dict:
    """Env for shelling out to claude -p — strip nested-Claude sentinels
    so the call falls back to the user's stored OAuth credentials."""
    env = dict(os.environ)
    if env.get("CLAUDECODE"):
        for k in list(env.keys()):
            if (
                k in ("CLAUDECODE", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")
                or k.startswith("CLAUDE_CODE_")
                or k.startswith("CLAUDE_AGENT_")
            ):
                env.pop(k, None)
    return env


def revalidate_inferred_llm(
    claim_raw: str, new_source_text: str, anchor: str | None,
) -> tuple[str, str]:
    """Stage 3: ask Claude whether the INFERRED claim is still supported
    by the new source content. Called for any INFERRED claim that passed
    the cheap anchor check (Stage 2), when --llm is set on the CLI.

    The round-1 cleanup removed the difflib gray-zone band that previously
    gated this call; we now invoke the LLM for every survivor of Stage 2.

    Returns (status, detail) where status is "pass"/"fail"/"llm_failed".
    """
    section_hint = ""
    anchors = collect_anchors_and_sections(new_source_text)
    if anchor and anchor in anchors:
        section_hint = f"\n\n## Anchored section (#{anchor})\n\n{anchors[anchor][:3000]}"
    prompt = (
        "You are validating whether a wiki claim is still supported by its "
        "cited source after the source content changed.\n\n"
        f"## Claim definition\n\n{claim_raw}\n\n"
        f"## Current source content (truncated to 5000 chars)\n\n"
        f"{new_source_text[:5000]}"
        f"{section_hint}\n\n"
        "Answer with exactly one line in this format:\n"
        "  VERDICT: PASS — <one-clause reason the claim is still supported>\n"
        "  or\n"
        "  VERDICT: FAIL — <one-clause reason the claim is no longer supported>\n"
        "\nDo not output any other text. PASS means a careful reader would "
        "consider the claim's load-bearing assertions to still hold up given "
        "the current source; FAIL means the source no longer says what the "
        "claim asserts."
    )
    try:
        proc = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions", prompt],
            capture_output=True, text=True, env=_claude_env(), timeout=60,
        )
    except FileNotFoundError:
        return ("llm_failed", "claude CLI not on PATH")
    except subprocess.TimeoutExpired:
        return ("llm_failed", "claude -p timed out after 60s")
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return ("llm_failed", f"claude -p exit {proc.returncode}: {(proc.stderr or '')[:200]}")
    # Parse VERDICT line.
    m = re.search(r"VERDICT:\s*(PASS|FAIL)\s*[—\-:]\s*(.+)", out, re.IGNORECASE)
    if not m:
        return ("llm_failed", f"could not parse VERDICT from response: {out[:200]}")
    verdict = m.group(1).upper()
    reason = m.group(2).strip()
    return ("pass" if verdict == "PASS" else "fail", f"LLM: {reason}")


def revalidate_one_drift(
    wiki_root: Path, drift: dict, use_llm: bool,
) -> dict:
    """Revalidate a single CHANGED drift entry. Returns enrichment dict
    to merge into the drift.

    Only CHANGED (default-mode) is supported today. live_changed has
    the live content available too but the comparison logic differs;
    extend later.
    """
    if drift.get("kind") != "changed":
        return {}  # only revalidate CHANGED for now
    source_path = drift.get("source")
    abs_path = wiki_root / source_path
    if not abs_path.is_file():
        return {"revalidation_error": f"source file missing on disk: {source_path}"}
    new_text = abs_path.read_text(encoding="utf-8", errors="replace")
    anchors = collect_anchors_and_sections(new_text)

    per_claim: list[dict] = []
    survivors_by_band: dict[str, int] = defaultdict(int)
    totals_by_band: dict[str, int] = defaultdict(int)

    for ci in drift.get("claims_impacted", []) or []:
        tag = ci.get("tag", "")
        totals_by_band[tag] += 1
        claim_record = {
            "claim_id": ci.get("claim_id"),
            "tag": tag,
            "file": ci.get("file"),
        }
        if tag == "EXTRACTED":
            status, detail = revalidate_extracted(
                {"quote": ci.get("quote")}, new_text,
            )
            claim_record["status"] = status
            claim_record["detail"] = detail
            if status == "pass":
                pass  # claim no longer impacts — survives = "doesn't impact"
            else:
                survivors_by_band[tag] += 1
        elif tag == "INFERRED":
            # Need the claim's first source pointer; not always in
            # claims_impacted (we have claim_id but not sources). Look it up
            # in the sidecar.
            full_claim = _lookup_claim(wiki_root, ci.get("file"), ci.get("claim_id"))
            if full_claim is None:
                claim_record["status"] = "lookup_failed"
                claim_record["detail"] = "couldn't find full claim record in sidecar"
                survivors_by_band[tag] += 1
            else:
                # Inject the cited source path into our pseudo-claim for
                # revalidate_inferred_cheap.
                pseudo = {"sources": full_claim.get("sources", [])}
                status, detail = revalidate_inferred_cheap(
                    pseudo, new_text, anchors,
                )
                if status == "pass" and use_llm:
                    # Optional stage 3 — ask Claude whether the claim still holds.
                    src = (pseudo["sources"] or [""])[0]
                    anchor = src.split("#", 1)[1] if "#" in src else None
                    llm_status, llm_detail = revalidate_inferred_llm(
                        full_claim.get("raw", ""), new_text, anchor,
                    )
                    status, detail = llm_status, llm_detail
                claim_record["status"] = status
                claim_record["detail"] = detail
                if status != "pass":
                    survivors_by_band[tag] += 1
        else:
            # AMBIGUOUS — always drop. Weak signal not worth gating severity on.
            claim_record["status"] = "dropped_ambiguous"
            claim_record["detail"] = "AMBIGUOUS claims are not re-validated"
        per_claim.append(claim_record)

    # Recompute severity from surviving claims.
    if survivors_by_band.get("EXTRACTED", 0) > 0:
        new_severity = "high"
    elif survivors_by_band.get("INFERRED", 0) > 0:
        new_severity = "medium"
    else:
        new_severity = "low"

    # Summary line for DRIFT.md.
    parts = []
    for band in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
        if totals_by_band.get(band, 0) > 0:
            n_pass = totals_by_band[band] - survivors_by_band.get(band, 0)
            parts.append(f"{n_pass}/{totals_by_band[band]} {band}")
    summary = "; ".join(parts) if parts else "no claims to revalidate"

    return {
        "severity_original": drift.get("severity"),
        "severity_after_revalidation": new_severity,
        "revalidated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revalidation_summary": summary + " still validate",
        "revalidation_per_claim": per_claim,
        "revalidation_used_llm": use_llm,
    }


# --- Claim lookup helper ---

_CLAIMS_CACHE: dict[tuple[Path, str], list[dict]] = {}


def _lookup_claim(wiki_root: Path, file: str, claim_id: str) -> dict | None:
    key = (wiki_root, file)
    if key not in _CLAIMS_CACHE:
        _CLAIMS_CACHE[key] = load_claims_for_file(wiki_root, file)
    for c in _CLAIMS_CACHE[key]:
        if c.get("id") == claim_id:
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument(
        "--llm", action="store_true",
        help="Use claude -p as a stage-3 fallback for INFERRED claims "
             "that pass the cheap anchor-exists check. Costs API tokens. "
             "Requires Claude Code CLI on PATH.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    drift_path = wiki_root / "DRIFT.json"
    drift = load_json(drift_path)
    if drift is None:
        sys.exit("DRIFT.json missing — run source_diff.py first.")

    n_revalidated = 0
    n_downgraded = 0
    enriched: list[dict] = []
    for d in drift.get("drifts", []):
        enrichment = revalidate_one_drift(wiki_root, d, use_llm=args.llm)
        if enrichment:
            d.update(enrichment)
            n_revalidated += 1
            if (
                SEVERITY_RANK.get(enrichment.get("severity_after_revalidation"), 0)
                < SEVERITY_RANK.get(enrichment.get("severity_original"), 0)
            ):
                n_downgraded += 1
        enriched.append(d)
    drift["drifts"] = enriched
    drift["revalidation_run_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    drift["revalidation_used_llm"] = args.llm

    drift_path.write_text(
        json.dumps(drift, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Append a re-validation footer to DRIFT.md (the JSON is the
    # machine-readable source of truth and has already been written above;
    # we don't re-render the MD body — just append a summary footer so the
    # downgrade decisions are visible in the rendered drift view).
    # Re-rendering the whole MD properly is for a follow-up.

    md_path = wiki_root / "DRIFT.md"
    existing_md = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""

    footer = ["", "---", "", "## Re-validation results (stage 2 / 3)", ""]
    if not n_revalidated:
        footer.append("_No CHANGED drift entries to re-validate._")
    else:
        footer.append(
            f"_Re-ran per-claim checks against {n_revalidated} CHANGED entry/entries. "
            f"{n_downgraded} severity downgrade(s) after re-validation_"
            + (" (LLM-assisted)" if args.llm else " (cheap stack only)")
            + "._"
        )
        footer.append("")
        for d in enriched:
            if "severity_after_revalidation" not in d:
                continue
            orig = d.get("severity_original", "?")
            new = d.get("severity_after_revalidation", "?")
            arrow = "→" if orig != new else "="
            footer.append(
                f"- `{d.get('id')}` `{d.get('source')}`: "
                f"**{orig}** {arrow} **{new}** "
                f"({d.get('revalidation_summary', '')})"
            )
    md_path.write_text(existing_md + "\n".join(footer) + "\n", encoding="utf-8")

    if not args.quiet:
        print(
            f"revalidated {n_revalidated} drift(s); {n_downgraded} downgraded "
            + ("(LLM-assisted)" if args.llm else "(cheap stack only)"),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
