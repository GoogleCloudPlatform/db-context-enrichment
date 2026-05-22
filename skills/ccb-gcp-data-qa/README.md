# gcp-data-qa

A Claude Code skill that wraps Google Cloud's **Conversational Analytics
API** (`geminidataanalytics.googleapis.com`, also marketed as the
"Gemini Data Analytics API") so you can ask natural-language questions
about a customer's BigQuery data and get back the answer, the SQL
Gemini wrote, and the underlying data.

Currently in **Preview** (free during preview; BigQuery query costs still
apply).

## Why bundle this with the wiki-builder skill

This skill works two ways:

- **Standalone (Mode A)** — you specify the BigQuery tables explicitly.
  Useful for one-off questions when no wiki has been built.
- **Wiki-grounded (Mode B)** — you point at a per-customer wiki produced
  by [the customer-context-builder skill](../customer-context-builder/),
  and this skill auto-extracts the table list AND composes a rich system
  instruction from the wiki's narrative (operational warnings, deprecated
  tables, partition gotchas, naming conventions). The agent's SQL is
  notably better with this context — that's the value-add of having
  built the wiki.

## Install

```bash
# From the repo root:
ln -s "$PWD/skills/gcp-data-qa" ~/.claude/skills/gcp-data-qa

# Python deps:
pip install -r skills/gcp-data-qa/scripts/requirements.txt
```

## Auth

Same gcloud / ADC stack as the customer-context-builder skill:

```bash
gcloud auth login
gcloud auth application-default login    # OR export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json

# One-time per project:
gcloud services enable geminidataanalytics.googleapis.com --project=<your-project>
```

## Use

In Claude Code, ask in natural language:

> Ask the acme-prod-123 data: what was Q1 revenue by channel?

If a wiki for that customer exists at `./customer-context/context/acme-prod-123/`,
the skill will use it (Mode B). Otherwise it'll ask which tables to consider.

Or directly via the wrapper:

```bash
# Mode A — explicit tables
python3 skills/gcp-data-qa/scripts/data_qa.py \
  --project=acme-prod-123 \
  --table=acme-prod-123:acme_analytics.fact_orders_daily \
  --table=acme-prod-123:acme_analytics.dim_users \
  --question="What was total revenue last 30 days, broken down by country?"

# Mode B — wiki-grounded
python3 skills/gcp-data-qa/scripts/data_qa.py \
  --project=acme-prod-123 \
  --wiki-dir=./customer-context/context/acme-prod-123 \
  --question="Which channel drove the most paid revenue last week?"
```

## Output

JSON to stdout (see `SKILL.md` for the schema). Pass `--output-file=PATH`
to also write a human-readable markdown transcript.

## Layout

```
skills/gcp-data-qa/
├── SKILL.md
├── README.md
├── scripts/
│   ├── check_prereqs.sh   # auth + API + SDK preflight
│   ├── data_qa.py         # the wrapper
│   ├── wiki_parser.py     # Mode B: parse a wiki dir → (tables, system instruction)
│   └── requirements.txt
└── examples/              # populated after smoke test
```

## Status

- v0.3 — initial scaffold; smoke-tested against the same `context-repo-building`
  sandbox project the wiki-builder uses.
- Known limitation: only BigQuery datasources are supported in this
  wrapper (the API also supports Looker, AlloyDB, Cloud SQL, Spanner;
  add as needed).
