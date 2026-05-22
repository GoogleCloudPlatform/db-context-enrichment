# v0.2 design notes (historical, frozen at v0.2)

> **Status: historical.** This file is the redesign rationale from
> v0.2 and is **frozen at that snapshot**. Anything implemented after
> v0.2 (gap detection, drift, the Context Center, two-stage
> re-validation, etc.) is documented in the top-level
> [`README.md`](../../README.md), [`docs/ALGORITHMS.md`](../../docs/ALGORITHMS.md),
> and [`SKILL.md`](SKILL.md) — not here.


The user requested a redesign of the skill's output structure to a
recursive, agentic-retrieval-friendly layout (every directory has an
`index.md`; sources are first-class with verbatim "gists"; personal
context is split out from warehouse context). This file records the
interpretations I made to fill in the spec's ambiguities, so the
choices are reviewable rather than buried in code.

If any of these interpretations is wrong, the fix is local — change the
relevant agent prompt or template, re-run the smoke test, the structure
regenerates.

## The user's spec (for reference)

```
context/
    index.md            -- central directory; navigation always starts here
    data_warehouse.md   -- detailed explanation of the data warehouse itself
    retrieval_methods.md -- how to retrieve more context
    sources/
        index.md
        {source_name}.md
    {table_name}/
        index.md        -- entry point for understanding the table
        fields.md       -- detailed table field info
        lineage.md      -- provenance
        sources/
            index.md
            {source_name}.md
```

Plus: `personal_context/` for docs/sheets, "directly under the context/
root dir."

Index file format: `# Summary` (1-5 paragraphs), `# Index` (peer files +
descriptions), `# Child Indexes` (links + descriptions).

Source file format: `# Retrieved from` (source / lineage / abs path),
`# Gists` (literal snippets with titles).

## Interpretation 1 — Multi-customer layout

Customers nest under the top-level `context/` directory, fitting the
recursive pattern naturally. Top-level `index.md` is a directory of
customers; each customer's subtree is the structure described above.

```
<output-dir>/
└── context/
    ├── index.md                    # lists customers
    └── {customer-name}/
        ├── index.md
        ├── data_warehouse.md
        ├── retrieval_methods.md
        ├── sources/
        ├── {table_name}/
        └── personal_context/
```

**Alternative considered:** `{customer-name}/context/...` (per-customer
tree). Rejected — produces N parallel `context/` roots which loses the
"single navigation entry point" property the user emphasized.

## Interpretation 2 — `personal_context/` location

Lives **inside each customer's directory**, as a sibling of the table
dirs. Rationale: the docs/sheets are about a specific customer, not
shared across customers, so per-customer placement is natural.

```
context/{customer-name}/personal_context/
    index.md
    internal_notes.md             # synthesis across docs+sheets
    sources/
        {doc_or_sheet}.md         # one per source, with verbatim gists
```

**Alternative considered:** `context/personal_context/` at the very top
(treating personal context as cross-customer). Rejected for the same
reason — content is customer-scoped.

## Interpretation 3 — `data_warehouse.md` vs `{table}/index.md`

- **`data_warehouse.md`**: warehouse-wide narrative. The 1-3 paragraph
  story of what the customer is building, the dataset/table layout in
  aggregate, governance posture, recent query-pattern themes,
  cross-source operational stories. Does **not** duplicate per-table
  detail — links to per-table dirs instead.
- **`{table}/index.md`**: per-table overview. What this table is for,
  who owns it, how it's used (referenced in which sheets/docs/queries),
  its grain, its partitioning, links to `fields.md` / `lineage.md` /
  `sources/`.

This split lets a downstream LLM load only what it needs: the
warehouse narrative for "what does this customer do?", a single
table's index for "tell me about `fact_orders_daily`".

## Interpretation 4 — `retrieval_methods.md`

Customer-specific instructions for how a downstream LLM should *fetch
more* context if it needs to. Includes:

- The customer's project ID, BigQuery region, Drive folder IDs
- Concrete commands (with placeholders): `bq show --schema PROJECT:DS.TBL`,
  `gcloud dataplex assets list ...`, etc.
- Notes on auth requirements (ADC scopes, gcloud account)
- Pointers to `sources/` for the snapshots already gathered

**Alternative considered:** generic GCP retrieval guide (same for every
customer). Rejected — the value is in the customer-specific values
(project ID, region, folder IDs, dataset name). Otherwise it's noise.

## Interpretation 5 — `{fields}.md` filename

Literal `fields.md`. The user wrote `{fields}.md` in braces but I read
that as illustrative ("a file named after the concept of fields"), not
templated.

## Interpretation 6 — what's a "source"

A source is **one retrieval that produced data the doc relies on**.
Each source file points to its origin and includes verbatim "gists"
that capture the load-bearing snippets.

Per-table `sources/`:
- `bq_show_schema.md` — `bq show --schema` invocation, with the JSON
  schema as a gist
- `bq_query_patterns.md` — JOBS_BY_PROJECT query, with the top patterns
  hitting this table verbatim
- `dataplex_catalog_entry.md` — if Dataplex has a catalog entry for
  this table, the entry as a gist
- `pipeline_design_doc.md` — paragraphs from the internal design doc
  that mention this table verbatim

Top-level (warehouse) `sources/`:
- `bq_dataset_list.md`, `bq_jobs_by_project.md`,
  `dataplex_lakes_list.md`, `dataplex_aspect_types_list.md`, etc.
- `internal_design_doc_overview.md` — paragraphs that describe the
  warehouse generally (vs. one specific table)

`personal_context/sources/`:
- One file per Doc or Sheet, with the most useful verbatim excerpts
  (already what the old `gdocs.md`/`gsheets.md` did, just per-source
  instead of bundled)

## Interpretation 7 — sub-agent decomposition

Old (v0.1): four parallel sub-agents per source (BigQuery, Dataplex,
Google Docs, Google Sheets) + a synthesizer. Each agent produced a
single bundled markdown.

New (v0.2): **four sub-agents per customer**, run in a specific order:

1. **`personal_context_agent`** — handles Google Docs + Sheets
   together. Emits `personal_context/internal_notes.md` and
   `personal_context/sources/*.md`. Combining is natural — both are
   "internal team notes about the customer." Runs **first**.
2. **`warehouse_agent`** — handles BigQuery + Dataplex together. Reads
   both surfaces and emits the full warehouse subtree (`data_warehouse.md`,
   `retrieval_methods.md`, top-level `sources/*.md`, and per-table
   `{table}/{fields,lineage}.md` + `{table}/sources/*.md`). Combining
   BQ and Dataplex makes sense because both surfaces describe the same
   physical artifacts and the per-table `lineage.md` should pull from
   both. Runs **after personal_context** so it can cite verbatim
   quotes from `personal_context/sources/*.md` in its narrative files.
3. **`indexer_agent`** — runs after warehouse, walks the entire tree,
   generates every `index.md`. Centralizing index generation
   guarantees a consistent format.
4. **`critic_agent`** — runs last, walks the wiki, writes a
   structured `CRITIQUE.md` with severity-ranked issues (format
   violations, fabrications, weak narrative, completeness gaps).
   Doesn't fix anything — flags. The user (or a subsequent re-run)
   handles fixes.

**Why serialize personal_context → warehouse instead of running them
in parallel?** Initial v0.2 ran them in parallel for max
throughput, but the critic's first pass uncovered a real bug: the
warehouse agent wrote "personal_context is empty" claims that became
false the moment personal_context finished. Tightening the warehouse
prompt to "ls personal_context first" wasn't enough — there was still
a race. Serialization eliminates the race entirely; the latency cost
(~4-5 minutes for personal_context running before warehouse instead
of alongside it) is worth the correctness win. **Cross-customer
parallelism is preserved** — for N customers, all N personal_context
agents run in parallel, then all N warehouse agents in parallel,
etc.

After all four sub-agents complete for all customers, the
orchestrator may optionally run `scripts/gcs_upload.py` to mirror
the generated tree to a GCS bucket (controlled via `gcs_bucket` in
the manifest, or a CLI flag). This is a script invocation, not a
sub-agent.

## What's preserved vs. dropped from v0.1

**Preserved data:**
- All BigQuery info (datasets, tables, schemas, query patterns,
  scheduled queries) — just sliced per-table instead of bundled
- All Dataplex info — augments `data_warehouse.md` (governance) and
  per-table `lineage.md`
- All Doc/Sheet content — moved to `personal_context/`
- The cross-source synthesis (the "Cross-source observations" section
  that was the v0.1 highlight) — folded into `data_warehouse.md` and
  per-table `index.md` files

**Dropped:**
- The bundled `bigquery.md` / `dataplex.md` / `gdocs.md` / `gsheets.md`
  files — replaced by the new tree
- The single per-customer `WIKI.md` — replaced by `data_warehouse.md`
  + per-table indexes + the index-of-indexes at customer root

## What I'm explicitly NOT doing in v0.2

- **Incremental regeneration** (only re-run what changed). v0.2 always
  regenerates the whole tree.
- **Helper scripts for `bq` / `gcloud`.** The v0.1 ones were broken; for
  v0.2 the agents call the CLIs directly. Can revisit.
- **Critic auto-fix loop.** The critic flags but doesn't re-run upstream
  agents to fix issues. v0.3 could orchestrate a fix-and-re-critique
  loop.

## Mid-flight additions (added during v0.2 implementation)

These weren't in the original spec but were added in the same session:

- **`critic_agent`** — runs after the indexer, writes a severity-ranked
  `CRITIQUE.md`. Surfaced the warehouse/personal_context ordering bug
  on the very first run; led to the serialization fix above.
- **`scripts/gcs_upload.py`** — thin wrapper around `gcloud storage
  rsync` to mirror the generated tree to a GCS bucket. Auth uses the
  same gcloud / ADC stack the rest of the skill uses. Configurable via
  `gcs_bucket` in the manifest (see
  [examples/customer_manifest.example.yaml](examples/customer_manifest.example.yaml))
  or as a CLI flag.

## How to override any of these

Each interpretation lives in exactly one place:

| Interpretation | Where to change |
|---|---|
| Multi-customer layout | `agents/indexer_agent.md` (top-level index) + `SKILL.md` (orchestration) |
| `personal_context/` location | `agents/personal_context_agent.md` (writes there) + indexer (links there) |
| `data_warehouse.md` vs table-index split | `agents/warehouse_agent.md` |
| `retrieval_methods.md` content | `agents/warehouse_agent.md` |
| `fields.md` filename | `agents/warehouse_agent.md` |
| What's a source | `templates/source_format.md` + the agents that emit sources |
| Sub-agent decomposition | `SKILL.md` (orchestration) + the three agent files |
