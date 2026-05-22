#!/usr/bin/env python3
"""Parse a customer-context wiki dir → (tables, system_instruction).

Used by the gcp-data-qa skill when invoked in --wiki-dir mode. The wiki
format is the recursive structure produced by the gcp-customer-context-builder
skill (every dir has an index.md; warehouse-level data_warehouse.md;
per-table {fields,lineage}.md; personal_context/ for internal notes).

Fail-soft: if the wiki is partially structured we pull what we can and
report gaps in the returned `warnings` list. Caller can decide whether
to proceed.

Usage as CLI (for testing):
    python3 wiki_parser.py /path/to/customer-context/context/<customer> [--project=PROJECT_ID_FALLBACK]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class WikiContext:
    project_id: str | None
    tables: list[str] = field(default_factory=list)
    system_instruction: str = ""
    warnings: list[str] = field(default_factory=list)


def parse_wiki(wiki_dir: Path, project_fallback: str | None = None) -> WikiContext:
    """Read a per-customer wiki dir, return tables + a composed system instruction."""
    ctx = WikiContext(project_id=project_fallback)

    if not wiki_dir.is_dir():
        ctx.warnings.append(f"wiki dir not found: {wiki_dir}")
        return ctx

    dw_path = wiki_dir / "data_warehouse.md"
    if not dw_path.is_file():
        ctx.warnings.append(f"missing {dw_path.name}; without it we can't enumerate tables")
        return ctx

    dw = dw_path.read_text(encoding="utf-8")

    ctx.project_id = _extract_project_id(dw) or project_fallback
    ctx.tables = _extract_tables(dw, ctx.project_id, wiki_dir)
    if not ctx.tables:
        ctx.warnings.append(
            "no tables extracted from data_warehouse.md — check that the file has a "
            "'## Table inventory' section with a markdown table listing tables"
        )

    ctx.system_instruction = _compose_system_instruction(wiki_dir, dw, ctx.tables)
    return ctx


def _extract_project_id(dw_md: str) -> str | None:
    """Look for 'Project ID: `xyz`' or similar in data_warehouse.md."""
    patterns = [
        r"[Pp]roject\s*ID[:\s]+`([a-z][-a-z0-9]{4,28}[a-z0-9])`",
        r"GCP project\s+`([a-z][-a-z0-9]{4,28}[a-z0-9])`",
    ]
    for pat in patterns:
        m = re.search(pat, dw_md)
        if m:
            return m.group(1)
    return None


def _extract_tables(dw_md: str, project_id: str | None, wiki_dir: Path) -> list[str]:
    """Enumerate tables from the wiki's per-table subdirs (the structural
    source of truth). Each subdir containing a `fields.md` is a table; its
    dirname is the table name. Dataset is inferred from data_warehouse.md
    by looking for explicit `dataset.table` references whose `table` half
    matches one of the discovered subdirs.

    Why subdir-only (not regex over prose): table names mentioned inline
    are often `table.column` references (e.g., `fact_orders_daily.order_date`)
    that look indistinguishable from `dataset.table` to a regex. The wiki
    structure encodes the truth unambiguously.
    """
    if not project_id:
        return []

    table_dirs: list[str] = []
    for sub in sorted(wiki_dir.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name in ("sources", "personal_context"):
            continue
        if (sub / "fields.md").is_file():
            table_dirs.append(sub.name)

    if not table_dirs:
        return []

    # Infer dataset, trying several patterns in order of specificity.
    # Strategy 1: a backtick-fenced `<id>.<table_name>` ref where table_name
    # is one of our known table dirs.
    dataset = None
    for tname in table_dirs:
        m = re.search(rf"`([a-z_][a-z0-9_]+)\.{re.escape(tname)}`", dw_md)
        if m:
            dataset = m.group(1)
            break

    # Strategy 2: 'dataset' (case-insensitive) followed by anything non-word
    # (comma, paren, space, "is", etc.) up to 60 chars, then a backtick-fenced
    # identifier. Handles "dataset, `acme_analytics`," and "dataset
    # (`acme_analytics`, US)" alike.
    if not dataset:
        m = re.search(r"dataset[^`a-z0-9_]{0,60}`([a-z_][a-z0-9_]+)`",
                      dw_md, re.IGNORECASE)
        if m:
            dataset = m.group(1)

    # Strategy 3: a per-table source file (bq_show_schema.md) usually lists
    # a fully-qualified `project:dataset.table` ref — pull from there.
    if not dataset:
        for tname in table_dirs:
            schema_src = wiki_dir / tname / "sources" / "bq_show_schema.md"
            if schema_src.is_file():
                m = re.search(
                    r"`(?:[a-z][-a-z0-9]{4,28}[a-z0-9]):([a-z_][a-z0-9_]+)\.[a-z_]",
                    schema_src.read_text(encoding="utf-8"))
                if m:
                    dataset = m.group(1)
                    break

    # Strategy 4: any backtick-fenced identifier that contains an underscore
    # AND appears in data_warehouse.md (most BQ datasets have underscores).
    if not dataset:
        for cand in re.findall(r"`([a-z][a-z0-9_]+_[a-z0-9_]+)`", dw_md):
            if cand not in table_dirs and "." not in cand:
                dataset = cand
                break

    if not dataset:
        return []

    return [f"{project_id}.{dataset}.{t}" for t in table_dirs]


def _compose_system_instruction(wiki_dir: Path, dw_md: str, tables: list[str]) -> str:
    """Compose a rich system instruction for the Conversational Analytics
    agent by pulling load-bearing context from across the wiki — customer
    overview, per-table notes/fields/lineage, personal team context (the
    wiki's internal_notes synthesis), cross-source operational stories,
    and naming conventions.

    Sections are emitted in priority order so that if the API later truncates
    the instruction, the most important context is preserved."""
    parts: list[str] = []

    # 1. Customer overview (always first — it's the orientation)
    cust_index = wiki_dir / "index.md"
    if cust_index.is_file():
        summary = _extract_section(cust_index.read_text(encoding="utf-8"), "Summary")
        if summary:
            parts.append(f"# Customer overview\n{summary.strip()}")

    # 2. Tables list (redundant with datasource_references but useful as NL anchor)
    if tables:
        parts.append("# Tables available\n" + "\n".join(f"- `{t}`" for t in tables))

    # 3. Per-table narrative summaries — operational warnings (deprecated,
    #    partition issues, etc.) that make the agent's SQL smarter
    table_notes: list[str] = []
    for table_ref in tables:
        table_name = table_ref.rsplit(".", 1)[-1]
        idx = wiki_dir / table_name / "index.md"
        if idx.is_file():
            summary = _extract_section(idx.read_text(encoding="utf-8"), "Summary")
            if summary:
                table_notes.append(f"## `{table_name}`\n{summary.strip()}")
    if table_notes:
        parts.append("# Per-table notes (read carefully — these constrain valid SQL)\n" +
                     "\n\n".join(table_notes))

    # 4. Per-table field schemas (NEW — column descriptions improve SQL
    #    accuracy: the agent can reason about column semantics, not just types)
    field_blocks: list[str] = []
    for table_ref in tables:
        table_name = table_ref.rsplit(".", 1)[-1]
        block = _extract_table_fields_condensed(wiki_dir, table_name)
        if block:
            field_blocks.append(block)
    if field_blocks:
        parts.append("# Per-table fields with descriptions\n" +
                     "_(only columns whose descriptions add semantic info beyond the column name)_\n\n" +
                     "\n\n".join(field_blocks))

    # 5. Personal team context (NEW — internal_notes synthesis carries
    #    the team's narrative about the customer: blockers, escalations,
    #    decisions, ownership)
    personal = _extract_personal_context_narrative(wiki_dir)
    if personal:
        parts.append(f"# Personal context (internal team notes)\n{personal.strip()}")

    # 6. Cross-source operational stories from data_warehouse.md
    cross = _extract_section(dw_md, "Cross-source operational stories") or \
            _extract_section(dw_md, "Cross-source observations")
    if cross:
        parts.append(f"# Cross-source operational context\n{cross.strip()}")

    # 7. Per-table lineage condensed (NEW — upstream/downstream is
    #    useful for "which table feeds which" questions and for picking
    #    the right table when several are candidates)
    lineage_blocks: list[str] = []
    for table_ref in tables:
        table_name = table_ref.rsplit(".", 1)[-1]
        block = _extract_table_lineage_condensed(wiki_dir, table_name)
        if block:
            lineage_blocks.append(block)
    if lineage_blocks:
        parts.append("# Per-table lineage (upstream/downstream relationships)\n" +
                     "\n\n".join(lineage_blocks))

    # 8. Conventions (look in any onboarding doc under personal_context)
    onboarding_dir = wiki_dir / "personal_context" / "sources"
    if onboarding_dir.is_dir():
        for f in sorted(onboarding_dir.glob("*onboarding*.md")):
            text = f.read_text(encoding="utf-8")
            conventions = _extract_section(text, "Conventions")
            if conventions:
                parts.append(f"# Naming and query conventions\n{conventions.strip()}")
                break

    # 9. Behavior block (last — the imperative)
    parts.append(
        "# Behavior\n"
        "Use ONLY the tables listed above. Honor the per-table warnings (deprecation, "
        "partition filters, schema gotchas) when generating SQL. Prefer active tables "
        "over deprecated ones unless the user explicitly asks for the deprecated table. "
        "When the personal context flags a tracker / KPI / blocker that's relevant to "
        "the question, cite it briefly in your answer (one sentence) so the asker can "
        "trace your reasoning. If a question can't be answered with the available "
        "tables, say so plainly and suggest what additional data would be needed."
    )

    return "\n\n".join(parts)


def _extract_table_fields_condensed(wiki_dir: Path, table_name: str) -> str | None:
    """Return a condensed fields block for one table — only columns whose
    description adds info beyond the column name itself. Skips columns
    with no description or boilerplate descriptions."""
    fields_path = wiki_dir / table_name / "fields.md"
    if not fields_path.is_file():
        return None
    md = fields_path.read_text(encoding="utf-8")
    # Look for a markdown table; pull rows that have a non-trivial description.
    lines = md.splitlines()
    in_table = False
    rows: list[tuple[str, str, str]] = []  # (col, type, desc)
    header_seen = False
    for line in lines:
        if not in_table:
            # Detect a header like | Column | Type | ... | Description |
            if "|" in line and ("description" in line.lower() or "desc" in line.lower()):
                in_table = True
                header_seen = True
                continue
        else:
            if not line.strip().startswith("|"):
                if header_seen and rows:
                    break
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            # Skip the separator row (| --- | --- | ...)
            if all(set(c) <= set("-: ") for c in cells):
                continue
            col = cells[0]
            ctype = cells[1] if len(cells) > 1 else ""
            desc = cells[-1] if len(cells) >= 3 else ""
            # Only include if description carries info (not empty, not (none),
            # not just punctuation, longer than ~5 chars)
            if desc and desc.strip() not in ("", "(none)", "—", "-") and len(desc.strip()) > 5:
                rows.append((col, ctype, desc))
    # Cap to 20 columns per table
    rows = rows[:20]
    if not rows:
        return None
    out = [f"## `{table_name}`"]
    for col, ctype, desc in rows:
        out.append(f"- `{col}` ({ctype}) — {desc}")
    return "\n".join(out)


def _extract_table_lineage_condensed(wiki_dir: Path, table_name: str) -> str | None:
    """Return condensed upstream/downstream lineage for one table."""
    lin_path = wiki_dir / table_name / "lineage.md"
    if not lin_path.is_file():
        return None
    md = lin_path.read_text(encoding="utf-8")
    upstream = _extract_section(md, "Upstream")
    downstream = _extract_section(md, "Downstream")
    if not upstream and not downstream:
        return None
    out = [f"## `{table_name}`"]
    if upstream:
        # Keep first 2 paragraphs; lineage docs often have block-quotes that
        # are useful but verbose
        upstream_short = "\n\n".join(upstream.split("\n\n")[:2]).strip()
        out.append(f"**Upstream:** {upstream_short}")
    if downstream:
        downstream_short = "\n\n".join(downstream.split("\n\n")[:2]).strip()
        out.append(f"**Downstream:** {downstream_short}")
    return "\n".join(out)


def _extract_personal_context_narrative(wiki_dir: Path) -> str | None:
    """Pull the load-bearing parts of personal_context/internal_notes.md —
    the team's narrative summary plus open blockers / escalations /
    decisions. Skip the per-doc/per-sheet enumeration (the agent doesn't
    need to know titles, just facts)."""
    notes = wiki_dir / "personal_context" / "internal_notes.md"
    if not notes.is_file():
        return None
    md = notes.read_text(encoding="utf-8")
    parts: list[str] = []

    # The Summary section (the headline narrative)
    summary = _extract_section(md, "Summary")
    if summary:
        parts.append(f"## Team narrative\n{summary.strip()}")

    # Open blockers / escalations / decisions — different docs use slightly
    # different headings; try a few.
    for heading in ("Open blockers / escalations / decisions",
                    "Open blockers and escalations",
                    "Open blockers",
                    "Blockers and escalations",
                    "Active issues"):
        section = _extract_section(md, heading)
        if section:
            parts.append(f"## Active blockers / escalations\n{section.strip()}")
            break

    return "\n\n".join(parts) if parts else None


def _extract_section(md: str, heading: str) -> str | None:
    """Return the markdown of the section under `# Heading` or `## Heading`,
    up to the next heading of equal-or-higher level.
    Match is case-insensitive and ignores trailing punctuation in the heading."""
    # Normalize heading for matching
    pattern = re.compile(
        r"^(#{1,6})\s+" + re.escape(heading) + r"\b.*?$",
        re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(md)
    if not m:
        return None
    level = len(m.group(1))
    start = m.end()
    # Find the next heading of equal-or-higher level
    next_pat = re.compile(rf"^#{{1,{level}}}\s+", re.MULTILINE)
    nm = next_pat.search(md, pos=start)
    end = nm.start() if nm else len(md)
    return md[start:end].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wiki_dir")
    ap.add_argument("--project", help="fallback project ID if data_warehouse.md doesn't mention one")
    ap.add_argument("--print-instruction-only", action="store_true",
                    help="print just the system instruction (for inspection)")
    args = ap.parse_args()

    ctx = parse_wiki(Path(args.wiki_dir), project_fallback=args.project)

    if args.print_instruction_only:
        print(ctx.system_instruction)
        return

    out = asdict(ctx)
    print(json.dumps(out, indent=2))
    if ctx.warnings:
        print("warnings:", file=sys.stderr)
        for w in ctx.warnings:
            print(f"  - {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
