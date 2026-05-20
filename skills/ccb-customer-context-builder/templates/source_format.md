# Source file format

A "source" is **one retrieval that produced data the wiki relies on**.
Every claim in the wiki should be traceable to a source file. Source
files preserve verbatim "gists" — the exact snippets from the original
data — so a downstream LLM can quote authoritative material rather than
paraphrasing the wiki's prose.

Source files carry an additional `# Retrieved from` field, **`Content hash:`**, populated by the build (see `scripts/build_manifest.py`). The
build hashes the underlying source content (BQ schema JSON, Drive doc
body, Sheet rows) so a later run can detect drift. Agents leave this
field blank or omit it — the build fills it in.

## Required structure

```markdown
# Retrieved from

- **Source:** {URL, command, file path, or other origin identifier}
- **Lineage:** {how this was obtained — the command run, the API endpoint, etc.}
- **Absolute path:** {where the source artifact lives, if applicable}
- **Retrieved at:** {ISO 8601 UTC timestamp of when this snapshot was taken}
- **Content hash:** {sha256 of the underlying source content; left blank by the agent — the build fills this in}

# Gists

## {Gist Title} {#anchor-slug}

{Literal snippet — quoted verbatim from the source. Preserve formatting
where it carries meaning (code blocks, tables, lists). Do NOT paraphrase.}

## {Another Gist Title} {#another-anchor}

{Another verbatim snippet}
```

Each gist title carries a stable anchor (`{#anchor-slug}`) so narrative
files can cite into a specific gist. Anchors should be kebab-cased
and short — `{#data-flow}`, `{#open-issues}`, `{#sql-used}`. If a gist
title is omitted from cross-narrative citations, the build derives
the anchor from the title automatically.

## Writing guidelines

**Verbatim, not summary.** The wiki's prose layer summarizes; source
files preserve the raw material. If the source is a doc that says
"fact_orders_daily partitioning is broken; ~30% of partitions written
without filters", quote that line — don't write "the doc mentions
partition issues."

**Pick gists that are load-bearing.** A source file shouldn't dump the
entire source — pick the 2–6 snippets that any downstream LLM would
actually want to ground an answer on. Skip preamble, table-of-contents,
boilerplate.

**Code/SQL/JSON blocks belong in fenced code.** Preserve the language
hint where useful.

**Title gists by what's in them, not by source structure.** "Migration
cutover plan" beats "Section 2.3" — the title is what an agent searches
on.

**One source per file.** If a single Doc has both warehouse-wide
context and per-table context, it appears in two source files (one
under top-level `sources/`, one under `{table}/sources/`), each gisting
the relevant excerpts. Duplication is fine; cross-referencing keeps the
locality property.

## Example — BigQuery query patterns source

```markdown
# Retrieved from

- **Source:** BigQuery `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` for project `acme-prod-123`
- **Lineage:** `bq query --project_id=acme-prod-123 --nouse_legacy_sql --format=prettyjson` against the SQL below
- **Retrieved at:** 2026-05-04T22:18:00Z

# Gists

## SQL used

```sql
SELECT
  REGEXP_REPLACE(query, r'\d+', 'N') AS query_pattern,
  COUNT(*) AS run_count,
  ...
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND statement_type = 'SELECT'
GROUP BY query_pattern
ORDER BY run_count DESC
LIMIT 50
```

## Top patterns by run count (verbatim)

| query_pattern (truncated) | run_count | top_users | avg_slot_seconds |
|---|---|---|---|
| `SELECT order_date, SUM(revenue) ... fact_orders_daily GROUP BY order_date ...` | 3 | claude-skill-test@... | 0.4 |
| `SELECT channel, SUM(revenue) ... attribution_summary_vN ...` | 2 | claude-skill-test@... | 0.5 |
| `SELECT 'events_raw' AS t, COUNT(*) ...` | 1 | claude-skill-test@... | 0.3 |
```

## Example — Drive doc source

```markdown
# Retrieved from

- **Source:** Google Doc — https://docs.google.com/document/d/1ts4knSMoHWQjfAtWCJrywN1xOEA822xLKV_q07DU2JQ/edit
- **Title:** "Acme — Pipeline Design Doc (Q1 2026)"
- **Last modified:** 2026-05-05 by oscarkang24@gmail.com
- **Retrieved at:** 2026-05-04T22:18:00Z

# Gists

## Data flow

> 1. The web tracker writes raw events to `events_raw`. Append-only,
>    partitioned by `event_ts`. Volume in prod is ~10M rows/day.
> 2. A nightly ELT job materializes `fact_orders_daily` from a join of
>    events_raw + the orders source-of-truth in our OLTP.
> 3. The weekly attribution job reads `fact_orders_daily` and `dim_users`,
>    runs the data-driven attribution model (v2.3 as of this writing),
>    and writes weekly rollups to `attribution_summary_v2`.

## Open issues called out

> - fact_orders_daily partitioning is inconsistent: roughly 30% of
>   recent partitions were created without the partition filter,
>   causing full-table scans.
> - The `attribution_channel` column in fact_orders_daily uses the
>   last-touch logic, which is inconsistent with the v2 model.
```
