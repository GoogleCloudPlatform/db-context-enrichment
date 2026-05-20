---
name: skill-ccb-gcp-data-qa
description: Ask natural-language questions about a GCP customer's BigQuery data via Google Cloud's Conversational Analytics API (also known as the "Gemini Data Analytics API"). Returns the agent's reasoning, the SQL it generated, the underlying result data, and a final natural-language answer. Use this skill whenever the user wants to query BigQuery in plain English without writing SQL — e.g., "what was Q1 revenue by channel?", "which dashboards still hit attribution_summary_v1?", "top 10 users by lifetime value." Trigger on phrasings like "ask the data", "ask BigQuery", "Gemini for BigQuery", "Conversational Analytics", "natural language query", or any time the user wants an analytic answer that would otherwise require hand-written SQL. If a customer-context wiki exists from the gcp-customer-context-builder skill, this skill can read it via --wiki-dir to ground the agent in the customer's specific data semantics (deprecated tables, partitioning quirks, naming conventions) — producing notably smarter SQL than a context-free agent would write.
---

# GCP Data Q&A (Conversational Analytics API)

This skill lets you ask natural-language questions about a GCP
customer's BigQuery data. It wraps Google Cloud's Conversational
Analytics API (`geminidataanalytics.googleapis.com`, currently in
Preview), which:

- Takes a natural-language question + a list of BigQuery tables +
  (optionally) a system instruction — passed inline on every call via
  `ChatRequest.inline_context`, so no `DataAgent` resource is created
  or persisted in the project (stateless / agentless mode)
- Plans, generates SQL, executes it
- Streams back typed messages: the agent's THOUGHT process, PROGRESS
  steps, the SQL written, the result data, and a final natural-language
  ANSWER

## When to trigger

Anytime the user wants an analytic answer about BigQuery data without
writing SQL. Phrasings: "ask the data", "what's the answer to ...",
"how many ...", "which ...", "trend of ...", "top N ...".

If the user mentions a specific customer (e.g., "ask the Acme data:
...") AND a customer-context wiki exists at the expected path, prefer
the **wiki-grounded** invocation — the agent produces much better SQL
when it knows about deprecated tables, partition gotchas, and naming
conventions.

## Two invocation modes

### Mode A — explicit tables (works without any wiki)

User specifies the tables the agent should consider. Most ergonomic
for one-off questions when no wiki has been built.

```bash
python3 "$SKILL_DIR/scripts/data_qa.py" \
  --project=acme-prod-123 \
  --table=acme-prod-123:acme_analytics.fact_orders_daily \
  --table=acme-prod-123:acme_analytics.dim_users \
  --question="What was total revenue in the last 30 days, broken down by country?"
```

### Mode B — wiki-grounded (uses output from gcp-customer-context-builder)

The skill reads the per-customer wiki and:

- Auto-extracts the table list from `data_warehouse.md`'s table
  inventory section
- Builds a rich system instruction from the wiki's narrative —
  table descriptions, deprecation warnings, partition gotchas,
  cross-source operational notes, naming conventions

```bash
python3 "$SKILL_DIR/scripts/data_qa.py" \
  --project=acme-prod-123 \
  --wiki-dir=./customer-context/context/acme-prod-123 \
  --question="Which channel drove the most paid revenue last week?"
```

The agent then knows (e.g.) to prefer `attribution_summary_v2` over
`attribution_summary_v1` (deprecated), to add `WHERE order_date >= ...`
filters on `fact_orders_daily` (partition regression in flight), and
to use the `paid_search` channel name, not `Paid Search`. **This is
the value-add of having built the wiki.**

## Inputs

- `--project` (required) — GCP project hosting the BQ tables and the
  Conversational Analytics API
- One of:
  - `--table=PROJECT:DATASET.TABLE` (repeatable) — for Mode A
  - `--wiki-dir=PATH` — for Mode B (path to a per-customer wiki dir,
    typically `./customer-context/context/<customer>/`)
- `--question="..."` (required) — the natural-language question
- `--output-file=PATH` (optional) — also write a markdown transcript
  of the session to this file
- `--chart-html=PATH` (optional) — explicit path for the interactive
  Vega-Lite chart preview. If omitted, the wrapper auto-renders charts
  to a tempfile (or to a sibling of `--output-file` if that's set)
  whenever the agent emits chart specs. The resolved path comes back
  in the JSON as `chart_html_path`.
- `--max-turns=N` (optional, default 1) — for multi-turn conversations
  via the API's stateful `Conversation` resource. Default is single-shot.

## Workflow

You are the orchestrator. For most invocations, this is one bash call
+ pretty-printing — no sub-agents needed.

### Step 1 — Resolve inputs

Parse the user's request to determine:
- Project ID (required)
- Either explicit tables (Mode A) or a wiki dir (Mode B)
- The natural-language question

If the user says "ask the X data: Y" and a wiki dir for X exists at
`./customer-context/context/X/`, use Mode B. Otherwise Mode A and ask
the user which tables to consider.

### Step 2 — Verify prereqs

Run `$SKILL_DIR/scripts/check_prereqs.sh`. It validates:

- `gcloud` is authenticated
- The Conversational Analytics API is enabled in the target project
- ADC is set up (either user creds OR `GOOGLE_APPLICATION_CREDENTIALS`)
- Python SDK is installed (`google-cloud-geminidataanalytics`)

### Step 3 — Run the wrapper

`scripts/data_qa.py` does the work. It emits structured JSON to stdout:

```json
{
  "question": "...",
  "context_mode": "inline",
  "generated_at": "2026-05-06T...",
  "messages": [
    { "type": "THOUGHT", "text": "..." },
    { "type": "SQL", "text": "SELECT ..." },
    { "type": "DATA", "rows": [...], "schema": [...] },
    { "type": "FINAL_RESPONSE", "text": "Total revenue last 30 days was $..." }
  ],
  "duration_seconds": 4.3,
  "status": "success"
}
```

### Step 4 — Present to the user

Render the response in this order (don't dump raw JSON):

1. **The question** (echoed)
2. **What the agent thought** — collapsed by default, expand if the
   user asks "show your work"
3. **The SQL it wrote** — always shown (this is the auditable artifact)
4. **The result data** — first ~10 rows as a markdown table, with a
   note about row count if more
5. **The final answer** — the prose answer Gemini wrote
6. **Chart preview** — if `chart_html_path` is set in the payload, the
   wrapper has already rendered an interactive Vega-Lite preview at
   that path. Surface it as a clickable markdown link so the user can
   open it. Do not re-render or write a separate HTML file yourself.

If `--output-file` was given, write the same content as a markdown file
to that path so the session is archivable.

### Step 5 — Failures

Common failures and how to handle them:

- **API not enabled**: check_prereqs catches this; tell the user to run
  `gcloud services enable geminidataanalytics.googleapis.com --project=PROJECT`
- **Insufficient IAM**: the calling principal needs `bigquery.dataViewer`
  + `bigquery.jobUser` on the target tables, plus access to the
  Conversational Analytics API. Surface the exact role to grant.
- **Invalid table reference**: the chat call will reject the inline
  context with a clean error from the API; surface it directly.
- **Question can't be answered** (Gemini doesn't know how): the
  FINAL_RESPONSE will say so. Pass it through to the user.

## Wiki integration (Mode B) details

When `--wiki-dir` is set, `scripts/wiki_parser.py` reads the wiki and
returns `(tables, system_instruction)`:

- **Tables** are extracted from the table inventory in
  `<wiki-dir>/data_warehouse.md` — looks for the markdown table that
  lists every BQ table with its grain.
- **System instruction** is composed from:
  - The customer-root `index.md` Summary (what this customer does)
  - Each per-table `index.md` Summary (especially the operational
    warnings: deprecated, partition issues, etc.)
  - The `data_warehouse.md` "Cross-source operational stories" section
  - Naming conventions from any `personal_context/sources/*onboarding*.md`

The composed system instruction is what makes Mode B notably better
than Mode A. See `scripts/wiki_parser.py` for the exact extraction
logic — it's fail-soft (if the wiki is partially structured, we get
what we can and warn about gaps).

## Why no sub-agents

Unlike the customer-context-builder skill, this one is a single
synchronous call — there's no parallel data collection, no multi-step
synthesis, no quality critique to do. Just: prepare the request, call
the API, render the response. Adding a sub-agent layer would be ceremony
without benefit.

## Reference files

- [scripts/data_qa.py](scripts/data_qa.py) — the wrapper around `DataAgentServiceClient` + `DataChatServiceClient`
- [scripts/wiki_parser.py](scripts/wiki_parser.py) — Mode B: read a wiki, return tables + system instruction
- [scripts/check_prereqs.sh](scripts/check_prereqs.sh) — preflight (auth, API, SDK)
- [scripts/requirements.txt](scripts/requirements.txt) — `google-cloud-geminidataanalytics`, `PyYAML`
- [README.md](README.md) — install + usage from the command line
