---
name: skill-ccb-customer-context-builder
description: Build a personalized "LLM wiki" context repository for one or more GCP enterprise customers by orchestrating parallel sub-agents that pull from BigQuery (datasets, tables, schemas, recent query patterns), Dataplex (lakes, zones, catalog entries, data-quality scans), Google Docs (internal customer notes), and Google Sheets (tracking spreadsheets). Use this skill whenever the user wants to create, refresh, or expand a context repo / wiki / knowledge base for a GCP customer or list of customers — even when they don't explicitly say "wiki" — including phrasings like "build context for project X", "summarize what customer Y is doing on GCP", "pull together everything we know about these projects", "prep an LLM context for the Acme account", or "generate a customer brief from BigQuery + our docs". Output is a recursive directory of markdown files structured for agentic retrieval, with separate trees for the data warehouse and personal-team-context, every directory carrying an index.md, and verbatim "gist" source files preserving the underlying data.
---

# GCP Customer Context Builder

This skill orchestrates a multi-agent harness that produces a recursive
markdown wiki describing what a GCP enterprise customer is working on.
The wiki is structured for agentic retrieval — every directory has an
`index.md` that summarizes the directory and links to peers and
children, so a downstream LLM can navigate without loading the whole
tree.

## When to use

Trigger this skill when the user wants to assemble customer context
from GCP and Google Workspace sources. Typical inputs are one or more
GCP project IDs, optionally with a manifest mapping each project to
Drive folders containing internal team notes about that customer.

If the user gives only a vague request ("build me context for Acme"),
ask once for the list of project IDs and any Drive folder IDs, then
proceed.

## Inputs

The skill accepts inputs in two shapes:

1. **Bare project IDs** — e.g., `acme-prod-123 acme-staging-456`.
   Used when the user just lists projects in chat. If the user hasn't
   pinned Drive folders, the orchestrator runs **Drive discovery**
   (Step 1.5 below) to surface candidate docs and asks the user to
   pick. If discovery returns nothing useful, sub-agents fall back to
   fullText search using the project ID and customer name.
2. **Manifest YAML** (`customers.yaml`) — richer input, lets the user
   pin exact Drive folders and supply human-readable names. See
   [examples/customer_manifest.example.yaml](examples/customer_manifest.example.yaml).
   Per-customer Drive entries are still optional — any customer
   without `drive.docs_folder_id` / `drive.sheets_folder_id` goes
   through Drive discovery + picker.

If both are present, the manifest wins.

## Output structure

The output is a recursive tree, intentionally designed for *agentic
retrieval*. Every directory has an `index.md` with three sections
(`# Summary`, `# Index`, `# Child Indexes`) so a downstream agent can
land in any directory and decide what to load next without scanning
the whole tree.

The top-level layout is the **Context Center** layout the wiki-viewer
skill auto-detects to render all 5 tabs (Wikis · Tickets · Candidates ·
Skills · Drift). The four non-wiki dirs start empty — they get populated
by the viewer's server-side action endpoints (Rescan, Create-skill,
Re-scan drift) once the user starts using it. The builder just stages
the layout so the tabs are visible from day one.

```
<output-dir>/
├── wikis/
│   ├── index.md                          # Lists all customers
│   └── <customer>/
│       ├── index.md                      # Customer overview, links into the rest
│       ├── data_warehouse.md             # Warehouse-wide narrative (BQ + Dataplex synth)
│       ├── retrieval_methods.md          # How to fetch more from this customer's GCP
│       ├── sources/                      # Warehouse-level retrieval snapshots
│       │   ├── index.md
│       │   ├── bq_dataset_list.md
│       │   ├── bq_jobs_by_project.md
│       │   └── ...                       # one per retrieval performed
│       ├── <table_name>/                 # one dir per BigQuery table
│       │   ├── index.md
│       │   ├── fields.md                 # column-by-column schema
│       │   ├── lineage.md                # provenance (upstream/downstream, Dataplex)
│       │   └── sources/
│       │       ├── index.md
│       │       ├── bq_show_schema.md
│       │       └── ...                   # per-table retrieval snapshots
│       └── personal_context/             # team-internal notes about this customer
│           ├── index.md
│           ├── internal_notes.md         # narrative across all docs+sheets
│           └── sources/
│               ├── index.md
│               └── <doc-or-sheet-slug>.md  # one per Doc/Sheet, with verbatim gists
├── tickets/                              # Empty — viewer populates from user uploads
├── candidates/                           # Empty — viewer populates via /api/rescan
├── skills/                               # Empty — viewer populates via /api/create-skill
└── drift/                                # Populated on rebuilds (Step 3.6)
    └── <customer>/
        ├── DRIFT.md                      # Copied from <customer>/DRIFT.md
        └── DRIFT.json                    # Copied from <customer>/DRIFT.json
```

Two file conventions matter:

- **Index files** follow [templates/index_format.md](templates/index_format.md)
  exactly — three sections, descriptions optimized for an agent
  scanning the tree.
- **Source files** follow [templates/source_format.md](templates/source_format.md)
  — `# Retrieved from` (origin metadata) plus `# Gists` (verbatim
  snippets, never paraphrased). They're the citation layer the
  narrative files (data_warehouse.md, internal_notes.md, fields.md,
  lineage.md) implicitly refer to.

## Prerequisites

The user must have:

- **`gcloud` and `bq` CLIs installed** and authenticated: `gcloud auth
  login`. The `bq`/`gcloud` calls use the gcloud user account.
- **Auth for Drive/Docs/Sheets** — either Application Default
  Credentials via `gcloud auth application-default login --scopes=...`
  *or* `GOOGLE_APPLICATION_CREDENTIALS` pointing at a service-account
  JSON. (Service accounts have zero Drive storage quota on personal
  Gmail, so they can read shared folders but can't write new files —
  fine for the read-only skill, not for seeding test data.)
- **Python 3.9+** with deps in [scripts/requirements.txt](scripts/requirements.txt).

Run [scripts/check_prereqs.sh](scripts/check_prereqs.sh) at the start
of every invocation. If it exits non-zero, surface the missing piece
to the user and stop — don't push through with partial auth.

## Workflow

You are the orchestrator. For each customer, you spawn three sub-agents.

### Step 1 — Gather inputs and verify prereqs

1. Resolve the list of customers (project IDs + optional Drive folder
   IDs + optional human-readable names) from manifest or chat.
2. Run `scripts/check_prereqs.sh`. Stop on failure with a clear
   remediation message.
3. Resolve `SKILL_DIR` (the absolute path to this skill's installation;
   typically `~/.claude/skills/gcp-customer-context-builder/` or
   wherever the user cloned the repo). Sub-agents inherit the user's
   CWD, NOT the skill dir, so passing absolute paths is required.
4. Create the per-customer output dir: `<output>/wikis/<customer>/`.
5. Create the four Context Center placeholder dirs at the top level:
   `<output>/{tickets,candidates,skills,drift}/`. These start empty —
   the wiki-viewer populates them via its server-side action endpoints.
   Creating them up front ensures all 5 tabs render from day one.

### Step 1.5 — Drive discovery + picker (only if any customer lacks pinned Drive folders)

If every customer in this run has both `docs_folder_id` and
`sheets_folder_id` pinned in the manifest, **skip this step entirely**
and go straight to Step 2.

Otherwise, run discovery once per invocation (not per customer — the
output is reused across all customers that need it):

```bash
python3 "$SKILL_DIR/scripts/discover_drive_docs.py" \
  --max-recent=200 --max-excerpts=60
```

The script returns a JSON list of recently-viewed Docs and Sheets
with metadata, parent folder name, and a short content excerpt
(first ~800 chars for docs, tab names for sheets). It does NOT rank
or filter by customer — that's your job.

For each customer that lacks pinned folders:

1. **Rank candidates by relevance** to this customer's `PROJECT_ID`
   and `CUSTOMER_NAME` (and any `search_terms` from the manifest).
   Use the title, parent-folder name, owner email domain, and the
   excerpt. Strong signals: customer name in title or excerpt,
   project ID anywhere, recurring entity names (table names, owner
   emails) that match what the warehouse might surface.
2. **Show the user the top ~10–15 candidates** as a numbered list:

   ```
   Candidate docs/sheets for Acme Corp (acme-prod-123):

   1. [doc] Acme — Pipeline Design Doc (Q1 2026)
      folder: claude-skill-test-docs · owner: jordan@acme.example.com
      excerpt: "...end-to-end attribution pipeline for Acme Corp..."
   2. [sheet] Acme — Pipeline Health Tracker
      folder: claude-skill-test-sheets · tabs: pipeline_runs, open_issues
   ...

   Reply with the numbers to use (e.g., '1 2 4'), 'a' for all, or
   's' to skip Drive entirely for this customer.
   ```

3. **Wait for the user's pick.** Do not auto-select. If they reply
   `s`, leave `DOC_IDS` and `SHEET_IDS` unset for this customer; the
   personal_context agent will fall back to fullText search.
4. **Pass the picked IDs** to the personal_context agent via
   `DOC_IDS` and `SHEET_IDS` env vars (comma-separated lists,
   separated by kind). The agent's `Find candidates` step uses these
   directly — no folder listing.

If discovery's `warnings` field mentions the viewedByMe fallback
(typical with service-account auth), surface that one-liner to the
user before showing candidates so they know the signal is weaker.

If `stats.total` is 0, skip the picker and let the agent fall back
to fullText search.

### Step 2 — Personal context first, THEN warehouse

These two run **sequentially**, not in parallel. Why: the warehouse
agent's narrative files (`data_warehouse.md`, per-table `lineage.md`)
should cite personal_context source files when relevant. If warehouse
runs in parallel with personal_context, it can race ahead and write
"personal_context is empty" claims that become false the moment
personal_context finishes — a bug observed in early v0.2 smoke tests.

Run order per customer:

#### Step 2a — Personal context

| Sub-agent          | Prompt file                                                         | Writes under                                  |
|--------------------|---------------------------------------------------------------------|-----------------------------------------------|
| Personal context   | `$SKILL_DIR/agents/personal_context_agent.md`                       | `$CUSTOMER_DIR/personal_context/`             |

Inputs: `SKILL_DIR`, `PROJECT_ID`, `CUSTOMER_NAME`, `CUSTOMER_DIR`,
plus `DOCS_FOLDER_ID`, `SHEETS_FOLDER_ID`, `SEARCH_TERMS` (any of
these can be omitted).

#### Step 2b — Warehouse

| Sub-agent          | Prompt file                                                         | Writes under                                  |
|--------------------|---------------------------------------------------------------------|-----------------------------------------------|
| Warehouse          | `$SKILL_DIR/agents/warehouse_agent.md`                              | `$CUSTOMER_DIR/` (excluding personal_context) |

Inputs: `SKILL_DIR`, `PROJECT_ID`, `CUSTOMER_NAME`, `CUSTOMER_DIR`.

Use `subagent_type: "general-purpose"` for both. Each Agent prompt
must include a reminder that the agent writes files to disk and
returns a one-line summary in chat — NOT the file contents.

**Cross-customer parallelism is fine.** If you have N customers,
spawn N personal_context agents in parallel, wait for all, then spawn
N warehouse agents in parallel. The serialization is per-customer.

Critically: **neither agent writes any `index.md` files.** Indexes
are produced by the indexer agent in Step 3.

#### Time budgets per sub-agent

To keep wiki-builder runs from blowing past expected wall-clock and
quota, each sub-agent prompt includes an explicit time budget. The
agent self-monitors via `date +%s` and degrades gracefully (writes
partial output with a `TRUNCATED` note in `Gaps and caveats`) once it
crosses the soft target. The orchestrator accepts partial output
rather than retrying — the critic surfaces what's missing.

| Sub-agent          | Soft target | Hard cap |
|--------------------|------------:|---------:|
| personal_context   |       4 min |    6 min |
| warehouse          |       8 min |   12 min |
| indexer            |       3 min |    5 min |
| critic             |       3 min |    5 min |

End-to-end target wall clock per customer: ~18 min upper bound (sum of
hard caps), typical ~12 min. Individual `bq`/`gcloud` calls inside
each agent are wrapped with `timeout 60` (or `timeout 30` for the
Drive helpers) so a single hung call can't blow the budget.

### Step 3 — Run the indexer

Once both Step 2 agents return for a customer, spawn the indexer:

| Sub-agent | Prompt file                              | Writes                       |
|-----------|------------------------------------------|------------------------------|
| Indexer   | `$SKILL_DIR/agents/indexer_agent.md`     | every `index.md` in the tree |

Inputs: `SKILL_DIR`, `CUSTOMER_NAME`, `PROJECT_ID`, `CUSTOMER_DIR`.

The indexer walks the tree depth-first, generates an `index.md` in
every directory conforming to the format spec.

### Step 3.5 — Build claims sidecar + source manifest + dep graph

After the indexer finishes for a customer, run three small scripts in
sequence to materialize the **per-claim verification + gap detection**
foundation. These run mechanically (no LLM), so the orchestrator
invokes them directly via `bash`/`python3` — no sub-agent.

```bash
python3 "$SKILL_DIR/scripts/claims_sidecar.py" --wiki-root="$CUSTOMER_DIR"
python3 "$SKILL_DIR/scripts/build_manifest.py" --wiki-root="$CUSTOMER_DIR"
python3 "$SKILL_DIR/scripts/dep_graph.py"      --wiki-root="$CUSTOMER_DIR"
python3 "$SKILL_DIR/scripts/gap_check.py"      --wiki-root="$CUSTOMER_DIR"
```

What each writes:

- `claims_index.json` + `<file>.claims.json` (one per narrative file) —
  every footnote citation parsed, with stable content-hash IDs and
  EXTRACTED / INFERRED / AMBIGUOUS bands. Also runs cross-file
  validation (anchors resolve, EXTRACTED quotes literal-substring
  match the cited gist).
- `source_manifest.json` — sha256 hash of every source file's content
  plus the source URI/lineage from its `# Retrieved from` block.
- `dep_graph.json` — nodes (narrative + source files) + edges
  (narrative → source via cited claims). Includes `cited_by` backlinks
  on source nodes.
- `GAPS.md` + `GAPS.json` — structural + coverage gaps, severity-sorted.

The wiki-viewer's Wikis tab reads `GAPS.json` to surface a per-page
side panel of gaps. The critic agent (next step) reads
`claims_index.json` to verify claim hygiene.

`gap_check.py` uses spaCy if `en_core_web_sm` is installed — bigger
recall on entity extraction. Without spaCy it falls back to regex over
BQ table-name patterns and emails; runs but with less recall on
narrative prose. To enable:

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

### Step 3.6 — Drift detection + rebuild plan (Phase 2, only on rebuilds)

On a fresh first build there's no drift to detect — `source_diff.py` is a
no-op. On any subsequent rebuild against an existing wiki tree, run:

```bash
python3 "$SKILL_DIR/scripts/source_diff.py"       --wiki-root="$CUSTOMER_DIR"
python3 "$SKILL_DIR/scripts/revalidate_drift.py"  --wiki-root="$CUSTOMER_DIR"
python3 "$SKILL_DIR/scripts/rebuild_plan.py"      --wiki-root="$CUSTOMER_DIR"

# Stage drift artifacts where the viewer's Drift tab looks for them.
# OUTPUT_DIR is the data root (parent of wikis/, candidates/, etc.) —
# i.e., CUSTOMER_DIR is "$OUTPUT_DIR/wikis/$CUSTOMER_NAME".
OUTPUT_DIR="$(dirname "$(dirname "$CUSTOMER_DIR")")"
DRIFT_DST="$OUTPUT_DIR/drift/$CUSTOMER_NAME"
mkdir -p "$DRIFT_DST"
cp "$CUSTOMER_DIR/DRIFT.md"   "$DRIFT_DST/DRIFT.md"   2>/dev/null || true
cp "$CUSTOMER_DIR/DRIFT.json" "$DRIFT_DST/DRIFT.json" 2>/dev/null || true
```

Skip the `cp` lines on a first build (the `|| true` tolerates the
missing files but you can just omit them entirely if you know
DRIFT.{md,json} wasn't written). The viewer's `/api/rescan-drift`
endpoint refreshes both the customer wiki AND the staged copies in one
shot — this is only the seed.

What each writes:

- `DRIFT.md` + `DRIFT.json` — sources that have **CHANGED** (sha256
  differs from manifest), been **DELETED**, or appeared **NEW** since
  last build. Severity is computed from claim impact: a CHANGED source
  cited by an EXTRACTED claim is HIGH (verbatim quote may now be wrong);
  INFERRED is MEDIUM; no claims is LOW. DELETED with any claim citing
  it is HIGH (orphaned citation).
- `revalidate_drift.py` — stage-2 re-validation of every CHANGED entry
  in `DRIFT.json`. EXTRACTED claims get a substring re-check against
  the new source content; INFERRED claims get an anchor-existence
  check; AMBIGUOUS claims drop. Severity is recomputed from the
  surviving claims and stamped back as `severity_after_revalidation`,
  which clears false-positive HIGHs from cosmetic edits (trailing
  newline, whitespace) without touching the underlying sha256 diff.
  Algorithm: see [docs/ALGORITHMS.md §7b](../../docs/ALGORITHMS.md).
- `rebuild_plan.json` — the set of narrative sections that need
  re-derivation, derived from DRIFT × `dep_graph.json`. Each action lists
  the section, its owning agent, the drifted sources it cites, and the
  claim IDs to re-validate. The orchestrator hands this plan to a
  focused sub-agent for surgical re-extraction (instead of rebuilding
  the whole wiki).

The wiki-viewer surfaces drift in a top-level **Drift** tab, with one-click
**Ack** per entry (reuses the `acknowledge_drift.py` script via the
`/api/acknowledge-drift` endpoint) and a **Re-scan drift** button per
customer.

`source_diff.py --live` re-fetches each source from its origin
(Google Doc body, Google Sheet, BigQuery schema, dataset listing) and
compares to the on-disk snapshot, surfacing **live_changed** /
**live_deleted** / **live_failed** entries on top of the local diff.
Concurrent fetches via `--live-workers=N` (default 4). Volatile sources
(JOBS_BY_PROJECT, etc.) and unsupported source kinds (Dataplex) are
skipped with a documented reason. Requires the same GCP auth used to
build the wiki originally:

```bash
python3 "$SKILL_DIR/scripts/source_diff.py" --wiki-root="$CUSTOMER_DIR" --live
```

Without `--live`, the default on-disk-hash comparison works in any
environment without GCP auth.

### Step 4 — Run the critic

After the indexer + claims/manifest/gap scripts finish for a customer,
spawn the critic:

| Sub-agent | Prompt file                              | Writes                       |
|-----------|------------------------------------------|------------------------------|
| Critic    | `$SKILL_DIR/agents/critic_agent.md`      | `$CUSTOMER_DIR/CRITIQUE.md`  |

Inputs: `SKILL_DIR`, `CUSTOMER_NAME`, `PROJECT_ID`, `CUSTOMER_DIR`,
`OUTPUT_PATH=$CUSTOMER_DIR/CRITIQUE.md`.

The critic walks the wiki, reads `claims_index.json` and `GAPS.md`,
and writes a structured critique with severity-ranked issues (format
violations, fabrications, weak narrative, completeness gaps, claim
citation hygiene). It does NOT fix anything — it flags. The user (or
a future re-run with a tightened prompt) handles fixes.

The critic can run in parallel with critics for other customers, but
must run after that customer's indexer + scripts complete.

### Step 5 — Write the top-level customer-list index

After all per-customer trees exist (and ideally after their critics
have written CRITIQUE.md), write `<output>/wikis/index.md` yourself
(no sub-agent needed) — it's a small file listing customers with
one-line summaries pulled from each customer's `index.md` summary
section. Conform to the index format spec.

### Step 6 — Optionally upload to GCS

If the user supplied a `--gcs-bucket=gs://bucket-name[/prefix]` arg
(or set `gcs_bucket` in the manifest), invoke
`scripts/gcs_upload.py` to mirror the local output tree to that
bucket. See [scripts/gcs_upload.py](scripts/gcs_upload.py) for the
exact CLI. Auth uses the same `gcloud` / ADC stack the rest of the
skill uses.

```bash
python3 "$SKILL_DIR/scripts/gcs_upload.py" \
  --local-dir=<output-dir>/wikis \
  --gcs-uri=gs://bucket-name/optional/prefix \
  --delete-extra  # mirror semantics — remove remote files not in local
```

If no bucket was supplied, skip this step silently.

### Step 7 — Report back

Print a short summary to the user:
- How many customers processed
- Per customer: which sub-agents succeeded / failed; critic grade + issue counts
- Total file count in the generated tree
- Path to the output directory
- GCS URI (if uploaded)

### Step 8 — Suggest the viewer (don't auto-launch)

The repo ships a sibling skill, `wiki-viewer`, that builds a
browseable HTML tree with sidebar navigation and serves it on a local
port. **Suggest** it in the report, but don't auto-launch — leaving a
server running that the user might not know about is a footgun.

Suggested phrasing:

> To browse the generated wiki interactively, you can invoke the
> `wiki-viewer` skill (or run `bash $SKILL_DIR/../wiki-viewer/scripts/serve_wiki.sh`
> directly).

If the user asks you to also open the viewer, hand off to wiki-viewer
rather than reimplementing it inline.

## Failure handling

A customer with no Dataplex resources, no Drive folder, or no internal
docs is a normal case, not an error — the relevant sub-agent should
write what it can and note the gap in its narrative file. The
orchestrator should treat empty-but-valid output as success.

A real failure (auth, network, permission) should be surfaced. The
sub-agent writes what it tried and what failed (in its `Gaps and
caveats` section), then exits with success unless it produced nothing
at all. The orchestrator reports per-source status to the user.

## Why this shape

**Recursive index.md everywhere** is for agentic retrieval — a
downstream agent reading any single `index.md` can decide which
subtree to load without traversing the whole repo. This trades a small
write cost (the indexer pass) for a large read cost reduction at
inference time.

**Sources separate from narrative** is for citation fidelity — the
narrative layer (`data_warehouse.md`, `internal_notes.md`, `fields.md`,
`lineage.md`) summarizes; the source layer preserves verbatim snippets
so a downstream LLM can quote authoritative material rather than
paraphrasing the wiki's prose. This matters for any answer that needs
to ground in the customer's actual words.

**Personal context separate from warehouse** is for both privacy and
relevance — internal team notes about a customer have different
access patterns and different downstream uses than the warehouse
schema itself. A retrieval agent answering "what does
fact_orders_daily contain?" wants `fact_orders_daily/fields.md`; an
agent answering "what's blocking the v2 migration?" wants
`personal_context/internal_notes.md`.

**Three sub-agents per customer (warehouse + personal_context +
indexer)** instead of four-by-source (BQ / Dataplex / Docs / Sheets):
the new structure couples BQ and Dataplex at the per-table level
(`lineage.md` pulls from both), so coupling them in one agent is
natural. Same for Docs and Sheets — both are "internal notes."
Centralizing index generation in one final agent guarantees format
consistency.

## Reference files

- [DESIGN_NOTES.md](DESIGN_NOTES.md) — interpretations made for v0.2 structure
- [templates/index_format.md](templates/index_format.md) — required format for every index.md
- [templates/source_format.md](templates/source_format.md) — required format for every source file
- [agents/warehouse_agent.md](agents/warehouse_agent.md) — BQ + Dataplex producer
- [agents/personal_context_agent.md](agents/personal_context_agent.md) — Docs + Sheets producer
- [agents/indexer_agent.md](agents/indexer_agent.md) — index.md generator
- [agents/critic_agent.md](agents/critic_agent.md) — quality reviewer (writes CRITIQUE.md)
- [examples/customer_manifest.example.yaml](examples/customer_manifest.example.yaml) — manifest schema
- [scripts/check_prereqs.sh](scripts/check_prereqs.sh) — auth / CLI / Python preflight
- [scripts/drive_search.py](scripts/drive_search.py) — Drive folder/keyword search
- [scripts/discover_drive_docs.py](scripts/discover_drive_docs.py) — Recent-docs discovery for the picker (Step 1.5)
- [scripts/gdocs_extract.py](scripts/gdocs_extract.py) — Google Doc body extractor
- [scripts/gsheets_extract.py](scripts/gsheets_extract.py) — Google Sheet metadata + sample
- [scripts/gcs_upload.py](scripts/gcs_upload.py) — mirror local output tree to a GCS bucket
- [scripts/claims_sidecar.py](scripts/claims_sidecar.py) — parse `[^cN]` footnote citations into per-file `<file>.claims.json` sidecars (Step 3.5)
- [scripts/build_manifest.py](scripts/build_manifest.py) — sha256 every source file → `source_manifest.json` (Step 3.5)
- [scripts/dep_graph.py](scripts/dep_graph.py) — section → claims → sources graph → `dep_graph.json` (Step 3.5)
- [scripts/gap_check.py](scripts/gap_check.py) — structural + coverage gap detection → `GAPS.md` + `GAPS.json` (Step 3.5). Add `--cluster-mode` to also run InfraNodus-style cluster gap detection (Louvain communities + betweenness centrality) — requires `networkx`
- [scripts/source_diff.py](scripts/source_diff.py) — drift detection: changed/deleted/new sources vs. manifest → `DRIFT.md` + `DRIFT.json` (Step 3.6). Supports `--live` (re-fetch from origin) and `--baseline=<name>` (compare to a pinned snapshot)
- [scripts/revalidate_drift.py](scripts/revalidate_drift.py) — stage-2 re-validation after `source_diff`: per-claim substring + anchor checks downgrade false-positive HIGHs from cosmetic edits; optional `--llm` adds a Claude verdict for INFERRED claims (Step 3.6)
- [scripts/rebuild_plan.py](scripts/rebuild_plan.py) — incremental rebuild scope: drift × dep_graph → `rebuild_plan.json` (Step 3.6)
- [scripts/acknowledge_drift.py](scripts/acknowledge_drift.py) — mark a drift entry handled so it stops appearing in DRIFT.md
- [scripts/live_fetchers.py](scripts/live_fetchers.py) — fetcher dispatch + LiveFetchError for `source_diff.py --live` (gdoc/gsheet/bq-schema/bq-list)
