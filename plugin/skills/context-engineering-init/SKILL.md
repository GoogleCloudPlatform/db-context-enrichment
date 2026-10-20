---
name: context-engineering-init
description: >-
  Configures the workspace and environment for database context engineering —
  manages Toolbox `tools.yaml` database connections, verifies runtime and GCP
  readiness (uv, Evalbench, ADC, Dataplex/GDA APIs, IAM), records workspace
  defaults once in `workspace_state.md`, initializes or clones each experiment's
  `experiment_state.md`, and diagnoses setup or MCP connection errors. Use when
  starting or cloning an experiment, connecting a new database, changing
  workspace defaults, or troubleshooting environment/MCP readiness failures.
  Don't use for generating evaluation datasets, authoring context items, or
  running evaluations directly.
---

# Skill: Environment & Connection Setup

## Goal
Ensure the caller's environment is ready for context-engineering work: Toolbox `tools.yaml` in place with at least one verified DB source, the workspace inputs recorded once in `.context-engineering/workspace_state.md` (Context Set project and location, Default DB source, enrichment sources, upload preference), each experiment's `experiment_state.md` initialised with its context set identity and active database so downstream skills read instead of re-asking, and (when asked or when downstream failures need diagnosis) runtime + GCP readiness verified. Manage `tools.yaml` and `workspace_state.md` on request; run any subset of checks on request.

## Prerequisites
- `gcloud` CLI on PATH.
- (Optional) Target GCP project id — if not provided, use ADC's default project.
- (Optional) Existing `tools.yaml` to amend rather than overwrite.

## Guidance

Pick the flow that matches the user's intent:

### Workspace layout (read first)

- `.context-engineering/tools.yaml` — the **single, shared** Toolbox configuration for the workspace. It may hold several DB sources; it is user-owned and never copied or duplicated. The Toolbox MCP server is launched by the client with this fixed path and reads it **only at startup**.
- `.context-engineering/workspace_state.md` — the **workspace inputs**: what the user told us once and every experiment reuses — Context Set `Project` and `Location`, the default `tools.yaml` `Default DB source`, `Enrichment sources`, and the `Auto-approve uploads` preference. Written **only by this skill**; every other skill reads it. Format and example: `context-engineering-hillclimb/references/layout.md`; precedence rules: *Inputs & resolution rules* in `context-engineering-workflow`.
- `.context-engineering/experiments/<experiment_name>/` — one directory per experiment (the *experiment root*) with two siblings: `dataset/` (golden set + splits, owned by dataset-generation) and `hillclimb/` (the run: `experiment_state.md`, `v<N>/`, `holdout_eval/`, `final_evaluation_report.md`). `hillclimb/experiment_state.md` is the **record of that run** — context set identity (resource names), `## Active Database` (which `tools.yaml` source and tools this experiment uses), datasets, iterations, verdict — never a second copy of the workspace inputs.
- **Legacy `autoctx/` migration**: If `.context-engineering/` does not exist yet (or is missing `tools.yaml` / `workspace_state.md`) and a legacy `autoctx/` directory (`autoctx/tools.yaml` or `autoctx/state.md`) is present in the workspace, inform the user and offer to migrate it by copying `autoctx/tools.yaml` to `.context-engineering/tools.yaml` (preserving file permissions) and carrying over any project and database source defaults from `autoctx/state.md` into `.context-engineering/workspace_state.md`.

### Manage `tools.yaml` (DB connections)

Three sub-workflows; all operate on `.context-engineering/tools.yaml`.

**Create new**
1. Identify the DB type. The supported databases are: Cloud SQL Postgres, Cloud SQL MySQL, AlloyDB Postgres, Spanner GoogleSQL (Graph supported), Spanner PostgreSQL (no Graph support), Cloud Bigtable, Firestore (MongoDB API), BigQuery, and Custom / Pluggable Engine (`type: custom`). Load the corresponding `references/<db_type>.md` for required fields.
2. Ask the user for every required field explicitly. Do not fill in missing values.
3. Generate the YAML from the template with the user's values.
4. Save to `.context-engineering/tools.yaml`. This path is fixed — the Toolbox MCP server reads it directly; any other path won't be picked up.

**Add to existing**
1. Identify the new DB type and a unique `<source>` name.
2. Ask for the required fields (same as Create).
3. Read the current `tools.yaml`.
4. Generate new `sources:` and `tools:` entries under the unique `<source>` name and append them.
5. Save the updated file.
6. If `.context-engineering/workspace_state.md` exists, ask whether the new source should become the workspace `Default DB source`; if yes, update that bullet and add a `## History` line.

**List existing**
1. Read `.context-engineering/tools.yaml`. If missing, tell the user.
2. Parse and list all names under `sources:`.

Validate the target source(s) standalone (Example: `uvx toolbox-server@1.14.0 --config .context-engineering/tools.yaml invoke <source>-list-schemas`) — no MCP restart needed for validation. On validation failure, drop into the checks below to diagnose (e.g., `DB source reachable`, `ADC configured`).

**Toolbox restart rule (always state it explicitly).** The `toolbox` MCP server only reads `tools.yaml` when it starts, so the agent's `<source>-*` tools do not change until it is restarted. Tell the user to restart it:
- after **every** write this skill makes to `tools.yaml`;
- whenever the user says they edited `tools.yaml` themselves;
- whenever a source listed in `tools.yaml` has no matching `<source>-list-schemas` / `<source>-execute-sql` tool in the agent's tool list (the tell-tale sign of a stale server).

Restart instructions per client:
- Gemini CLI: `/mcp reload`
- Claude Code: `/mcp` → `toolbox` → Reconnect (or `/quit` and relaunch)
- Antigravity CLI: `/mcp` → `toolbox` → Restart

### Record the workspace inputs (`workspace_state.md`)

Run this when `.context-engineering/workspace_state.md` is missing (first experiment in a workspace) or when the user asks to change a default. Everything here is asked **once per workspace**; downstream skills read the answers from the file and never re-ask.

1. **DB connection** — if `.context-engineering/tools.yaml` does not exist, run **Create new** above first (and give the restart reminder).
2. **Project** — the GCP project id the context sets are published in (default: ADC's project). At the same time check the **ADC quota project** (`quota_project_id` in `~/.config/gcloud/application_default_credentials.json`): if missing, stop and give the fix (`gcloud auth application-default set-quota-project <project>`); if it differs from `<project>`, tell the user that API calls are billed/authorized against `<quota>` while context sets live in `<project>`, and continue only if they confirm that is intended. The quota project is **not** recorded in the file.
3. **Location** — call `list_context_set_locations(projectId)` and ask, naming the purpose: *"Which location should be used for storing your context sets? Available: `<list>`."* If the user already named one, confirm it is in the list. Do not assume a default.
4. **Default DB source** — the `tools.yaml` source experiments use by default. One source in `tools.yaml` → record it **without asking**. Several → ask which one. (When a source is added later through **Add to existing**, ask whether it should become the default.)
5. **Enrichment sources** (optional) — material about the database that helps both the **evaluation dataset** (realistic questions) and the **initial context set** (business terms, join rules). Ask in plain words, no skill names: *"Do you have any design docs, application code, sample SQL queries or notes about this database that I should read when creating the evaluation questions and the initial context set? Share file paths, or say none."* Record the list, or `(none)`.
6. **Upload approval** — **always ask, never infer.** Ask once, verbatim and neutrally — no "recommended", "default" or any steer attached to either option: *"Improving the context set takes several rounds, and each round's draft version is uploaded to the Context Set server to be scored. Should I upload these draft iterations automatically, or pause for your approval before each upload to review the ContextSet manually first?"* Record `Auto-approve uploads: true` **only** when the user's answer to *this question* chooses automatic (e.g. "upload automatically", "auto-approve", "run unattended"). Everything else records `false` — no answer, an unsure answer, or any prompt wording that merely authorises a *specific* upload ("upload it once", "upload the baseline", "upload and poll to done"): that is consent for that one action, not a standing preference, and it does **not** replace the question. The `false` fallback is an internal safety rule, not something to present to the user as advice. Do not add caveats about end-of-run replacement here — that HITL is explained when it is relevant (existence probe, step 3 of the experiment flow).

Write the file in the format shown in `context-engineering-hillclimb/references/layout.md` and read the recorded values back in one short summary. **Only this skill writes `workspace_state.md`.** Every later change (a default the user asks to change, a new Default DB source) rewrites the bullet and appends one line under `## History` (`- **Updated**: <date> — <what changed>`).

### Initialise the experiment `experiment_state.md`

Run this when a user is starting a hill-climb experiment, or when a downstream skill routes here because `.context-engineering/experiments/<experiment_name>/hillclimb/experiment_state.md` is missing or incomplete. If `workspace_state.md` is missing, run **Record the workspace inputs** first. Everything below is asked **once**; downstream skills (`dataset-generation`, `bootstrap`, `hillclimb`, `evaluate`, `workflow`) read the answers from `experiment_state.md` and never re-ask. If the file already exists, only fill in the missing bullets — do not overwrite existing values or any `## Iteration Log`. If the file already contains `## Final:`, the experiment is **finished**: do not modify it; offer the clone flow below instead.

**Review the workspace inputs (when `workspace_state.md` already existed from an earlier setup — skip if you just created `workspace_state.md` in this turn).** Print the recorded inputs verbatim and ask **one** question:

> *"I'll use the inputs recorded in `.context-engineering/workspace_state.md` for this experiment:*
> *– Project `<project>`, location `<location>`*
> *– Default DB source `<source>` (`tools.yaml`)*
> *– Enrichment sources: `<list or none>`*
> *– Uploading draft iterations: `<automatically | pause for my approval before each>`*
> *Keep these, change some for this experiment only, or change the defaults?"*

- **Keep** → continue with step 1; `experiment_state.md` gets no copy of these values.
- **Change for this experiment only** → the experiment deviates without touching the file. DB source → recorded in `## Active Database` as usual (step 5). Enrichment sources → `Enrichment sources (this experiment): [...]` in `## Metadata`. Upload approval → `Auto-approve uploads (this experiment): <true|false>` (the same neutral draft-iterations question as above, answered for this run). Project/Location cannot be overridden per experiment — they are workspace defaults; if the user wants another project or location, that is a default change.
- **Change the defaults** → update `workspace_state.md` (History line), then continue.

**Clone mode** (follow-up to a finished experiment). Triggered when the user names a source experiment (e.g. *"cloned from `<source>` for context fixes / dataset expansion"*, usually via the hand-off card printed by `context-engineering-workflow`). Before step 1:
- Verify `.context-engineering/experiments/<source>/hillclimb/experiment_state.md` exists and has `## Final:`; read its `Final Context Set resource`, `## Active Database`, dataset bullets, verdict, and `.context-engineering/experiments/<source>/hillclimb/final_evaluation_report.md`.
- **Copy `golden.json` only**: `<source>/dataset/golden.json` → `.context-engineering/experiments/<experiment_name>/dataset/golden.json`. Never copy `splits/`, plans or audit reports — the new experiment must first incorporate the generalizability findings/recommendations from `<source>/hillclimb/final_evaluation_report.md` into the copied `golden.json` (adding the recommended query/phrasing/value variations) and **only after `golden.json` is updated** run `split_dataset` so it gets an uncontaminated `splits/holdout.json` while preserving the base domain distribution.
- Record both `- Source evaluation report: ./.context-engineering/experiments/<source>/hillclimb/final_evaluation_report.md` and `- Golden dataset: ./.context-engineering/experiments/<experiment_name>/dataset/golden.json (cloned; expand with recommendations from source evaluation report before split)` under `## Metadata` in `experiment_state.md` so `context-engineering-dataset-generation` reads the previous generalizability report, applies its recommended variations to `golden.json`, and splits only after expansion is complete.
- Pre-fill: `Seed Context Set resource` = source's published resource (`Final Context Set resource`, if it was published; otherwise the source's best local file); `## Active Database` = source's (same `tools.yaml` source — confirm it still exists in `tools.yaml`). Project/Location come from `workspace_state.md` like any other experiment. Record only the `Golden dataset` bullet — the split bullets are written by the dataset skill after `split_dataset`. Skip the DB connection questions.
- `Context set id` still defaults to the **new** experiment name (step 2), so the clone is a *fresh* context set and the source's published set is never touched.

**Existing-context-set mode** (the user wants to improve a context set that is already published). Triggered when the user supplies a resource name — *"improve / fix `projects/<p>/locations/<l>/<collection>/<id>`"*. Before step 1:
- **Parse it per the Resource naming rule** in `context-engineering-workflow`: `projectId` = segment after `projects`, `location` = segment after `locations`, `contextSetId` = last segment. **Do not validate or depend on the collection segment** (`contextSets` today, `entryGroups` later — both must work unchanged). If the string lacks that structure, ask the user to re-check it; never guess.
- Confirm it exists: `get_context_set(projectId, location, contextSetId)`. NOT_FOUND → tell the user and ask for a corrected name (do not create anything). Keep the response's `description` for the summary, and record its `databases` list **verbatim** (as returned, or `[]` if empty) under `## Active Database` as `- **Seed databases**: [...]`. This exists only so the final replacement can **append** to the existing association — the existing set's `databases` are never replaced by this experiment's.
- Record `Seed Context Set resource: <the supplied string, verbatim>`. The resource's own project and location are authoritative for this experiment (identity is always parsed from the resource names in `experiment_state.md`); if they differ from `workspace_state.md`, say so in the summary — do **not** edit `workspace_state.md`.
- Ask **one** question: *"Should the improved version replace `<supplied name>` (same name), or be published under a new name?"* Default for this flow: **same name**. Same name → `Context set id` = parsed `<context_set_id>` and `Final Context Set resource` = the supplied string verbatim (step 3 will then find it exists and set up the draft strategy). New name → continue with step 2 as usual.
- `v0` comes from the seed, not from bootstrap (hillclimb downloads it).

1. **Experiment name** — ask for a short slug (e.g. `retail-graph`). The experiment root is `.context-engineering/experiments/<experiment_name>/`; create it together with its `hillclimb/` sub-directory (`dataset/` is created by dataset-generation, or now if a golden set is being copied in). `experiment_state.md` is written at `<experiment_root>/hillclimb/experiment_state.md`.
2. **Context set id** — the name the **final** context set is published under. Default: the experiment name. Derive `Final Context Set resource` strictly per the **Resource naming rule** in `context-engineering-workflow` from `workspace_state.md`'s `Project` / `Location` (verbatim user string when one was supplied) — do not hardcode a path shape here.
3. **Existence probe → working-copy strategy.** Probe the bare id with `get_context_set(projectId=<project>, location=<location>, contextSetId=<context_set_id>)` and record the result as the `Draft Context Set resource` bullet; this single bullet tells hillclimb how to work:
   - **NOT_FOUND (fresh context set)** → record `Draft Context Set resource: (none — new context set; iterations upload to the final name)`. Tell the user: *"`<Final Context Set resource>` doesn't exist yet, so I'll build it in place: every iteration is uploaded under that name and the best one stays there at the end. No scratch copy, nothing to delete."*
   - **Exists** → record `Draft Context Set resource: <Final Context Set resource with its last segment replaced by <context_set_id>_draft>` (same collection segment). Tell the user — this is the only warning they get before the end: *"`<Final Context Set resource>` already exists. I will not touch it during the run: iterations go to `<Draft Context Set resource>`. At the end I'll run the holdout test on the draft, show you the current vs new results, and **ask** before replacing `<Final Context Set resource>` — and only if the new one is better. A replacement changes only its context payload; its existing database association is kept. Either way the draft is deleted afterwards (expect one `delete_context_set` call)."* If the user did **not** supply this resource as their seed (they just reused a name), also offer to pick a different `Context set id` instead; if they choose another name, re-probe.
4. **Seed Context Set resource** (optional; pre-filled in clone and existing-context-set modes) — an existing Context Set resource name to start from, recorded **verbatim** as `Seed Context Set resource: <resource name>` (parsed per the Resource naming rule; any collection segment accepted). Hillclimb downloads it once as `v0` and never writes to it during the loop. Otherwise record `Seed Context Set resource: (none — seeded from bootstrap)` or `Seed Context Set resource: (local file: <path>)`.
5. **Active database** — the `tools.yaml` source this experiment targets (the `Default DB source` from `workspace_state.md`, or the one chosen in the review step). Record under `## Active Database`: **Source Name**, **Type**, and **Tools** (the exact tool names declared for that source, e.g. `financial-list-schemas`, `financial-execute-sql`), so the experiment is self-describing even when `tools.yaml` holds several sources. The `databases` argument for `upload_context_set` is derived at upload time from this **Source Name** and the source's block in `tools.yaml` (mapping table under *Database association* in `context-engineering-workflow`). Only check that the block has the fields that mapping needs for its type (AlloyDB: project/region/cluster/instance/database; Cloud SQL: project/region/instance/database; Spanner: project/instance/database; Bigtable: project/instance; Firestore: project/database; BigQuery / custom: none — no database association is sent for these) and ask the user to complete `tools.yaml` if one is missing. For Spanner GoogleSQL, call `<source>-list-graphs` and record the property graph ids as `- **Graph Ids**: [...]` (`[]` if none) — `generate_evalbench_configs` reads this bullet. For BigQuery, record the tables in scope as `- **Table Ids**: [...]` (from `<source>-list-schemas`; at least one — the QueryData API requires explicit table references and `tools.yaml` has no place for them) — `generate_evalbench_configs` reads this bullet too. Before recording, confirm the `<source>-list-schemas` tool is visible in the agent's tool list; if the source is in `tools.yaml` but its tools are not visible, apply the Toolbox restart rule above first.
6. **Existing dataset** — the only dataset file a user (or a clone) can bring in is the golden set, and it must live at **`.context-engineering/experiments/<experiment_name>/dataset/golden.json`**. If the user has their own evaluation dataset, tell them that exact path (offer to copy their file there — never reference it from elsewhere) and record `Golden dataset: <path> (user-supplied; expand before split)` — a user file is a seed that goes through expansion, audit and split. If no file is present, leave the dataset bullets out. **Never record `Hillclimb dataset` / `Holdout dataset` here** — `dataset/splits/` is produced **exclusively** by `context-engineering-dataset-generation` via the `split_dataset` tool, and that skill writes those two bullets. If a user hands over pre-split files (`dev.json` / `test.json`, or a hand-made `splits/`), reject them and explain that only the single golden set can be provided and the `split_dataset` tool will produce `dataset/splits/`.

Write the file in the format shown in `context-engineering-hillclimb/references/layout.md` (a `## Metadata` section with the bullets above, then `## Active Database`). Confirm the path and the recorded values back to the user in one short summary.

### Verify environment (broad or scoped)

Run any subset of the checks below. Report `PASS` or `FAIL` per check. For any `FAIL`, propose a fix and ask the user for consent before executing anything mutating (installing packages, enabling APIs, changing IAM, writing files).

- **Broad verification** ("am I ready?") → run all checks.
- **Scoped diagnosis** (a downstream skill failed) → run only the checks whose `— required by …` line references the failing operation.

## Checks

Commands in parentheses are examples — the agent may use its own approach.

### Environment
- **`uv` installed** — required to run Toolbox and Evalbench via `uvx`. (Example: `uv --version`; install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.)
- **Evalbench reachable** — required by `context-engineering-evaluate`; verifying also warms the uvx cache so the first `evaluate` run is fast. (Example: `uvx google-evalbench@1.18.0 --help`.)

### GCP authentication
- **ADC configured** — required by every GCP API call (Context Set server, QueryData, Dataplex). (Example: `gcloud auth application-default print-access-token`; fix via `gcloud auth application-default login`.)
- **ADC quota project set** — required by Context Set server; the `X-Goog-User-Project` header is derived from it. Missing → 400 on upload/download. (Example: check `quota_project_id` in `~/.config/gcloud/application_default_credentials.json`, e.g. `python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/gcloud/application_default_credentials.json'))).get('quota_project_id'))"`; fix via `gcloud auth application-default set-quota-project <project>`.)

### GCP API enablement
- **Dataplex API** (`dataplex.googleapis.com`) — required by every Context Set tool (`list_context_set_locations`, `upload_context_set`, `get_context_set`, `delete_context_set`, `get_operation`). See the Context Set MCP Protocol in `context-engineering-workflow` for how these are used.
- **Gemini Data Analytics API** (`geminidataanalytics.googleapis.com`) — required by QueryData (used inside `context-engineering-evaluate`).

(Example: check enablement via `gcloud services list --enabled --project=<project>`; enable via `gcloud services enable <api> --project=<project>`.)

### GCP IAM (operational probes)
- **Context Set server connected** — the five Context Set tools (`list_context_set_locations`, `upload_context_set`, `get_context_set`, `delete_context_set`, `get_operation`) are served by the **remote Context Set MCP server** registered in the plugin manifests under the key `ctxset` (Google-credentials auth). Check that all five appear in your tool list. If they do not, do not continue the preflight: tell the user the remote server is not connected and give the fix — ADC present with a quota project (checks above), then reload MCP servers in the client (Antigravity: open the MCP panel; Gemini CLI: `/mcp refresh`). A `401`/`UNAUTHENTICATED` on the first call to any of these tools means the client could not mint an ADC token: re-run `gcloud auth application-default login`, then reload.
- **Context Set access** — required by every Context Set tool and by QueryData's context lookup. Probe by calling `get_context_set(projectId=<project>, location=<location>, contextSetId=preflight-probe-does-not-exist)` in the chosen `<location>` (or `us-central1` if not yet chosen) — a well-formed identity that is known not to exist. Interpret the outcome:
  - **NOT_FOUND** → the request was authenticated and authorized and reached the API; the probe **passes**. This is the expected result.
  - **UNAUTHENTICATED** → ADC is missing or expired; point the user back to the GCP authentication checks above.
  - **PERMISSION_DENIED** → surface the error verbatim and ask the user to request the appropriate Context Set IAM role from their IAM admin.
  - Anything else → surface the error verbatim; do not guess at the cause.
- **GDA access** — required by QueryData (used by `evaluate`). Probe by attempting a lightweight QueryData call in `<project>`. On 403, same handling.

### Workspace files
- **`tools.yaml` present** — required by every skill that reads database schemas (`bootstrap`, `evaluate`, `hillclimb`). Check `.context-engineering/tools.yaml` (the fixed path the Toolbox MCP server reads). Missing → run the Create sub-workflow above.
- **`workspace_state.md` present and complete** — required by every skill that starts or resumes an experiment. Check `.context-engineering/workspace_state.md` has `Project`, `Location`, `Default DB source`, `Auto-approve uploads` (enrichment sources may be `(none)`), that `Default DB source` names a source in `tools.yaml`, and that `Location` is still in `list_context_set_locations(Project)`. Missing → run **Record the workspace inputs** above; incomplete → ask only for the missing bullets.
- **Toolbox server in sync with `tools.yaml`** — required for the agent to see the sources. For every `kind: source` in `tools.yaml`, the corresponding `<source>-list-schemas` / `<source>-execute-sql` tools must be present in the agent's tool list. Any source present in the file but absent from the tool list → the server was started before that source was added (or the user edited the file by hand): **tell the user to restart the `toolbox` MCP server** (instructions above) and re-check.
- **Experiment source still configured** — required by every skill running inside an experiment. The **Source Name** under `## Active Database` in the experiment's `experiment_state.md` must exist in `tools.yaml`. Missing → the user removed or renamed it; ask them to restore it (or add it back via the Add sub-workflow) rather than silently picking another source.
- **DB source reachable** — required by any Toolbox invocation on that source. For each configured `<source>` in `tools.yaml`, verify Toolbox can list its schemas standalone. On failure, surface the error verbatim; common causes are ADC, wrong project/region, DB IAM, or network. (Example: `uvx toolbox-server@1.14.0 --config .context-engineering/tools.yaml invoke <source>-list-schemas`.)

## Rules
- Never execute mutating actions (`gcloud services enable`, `gcloud projects add-iam-policy-binding`, package installs, file writes) without explicit user consent — surface the exact command and let the user run it, or ask consent before running.
- ADC only for DB auth. Never write username/password into `tools.yaml`. Strongly recommend a **read-only** database principal / IAM role.
- `tools.yaml` always lives at `.context-engineering/tools.yaml` — one shared file per workspace; do not offer or accept a different path and never copy it into an experiment. If the file exists, ask whether to append or overwrite. Every write ends with the Toolbox restart reminder.
- `workspace_state.md` always lives at `.context-engineering/workspace_state.md` and is written **only by this skill**. It holds workspace inputs (Project, Location, Default DB source, Enrichment sources, Auto-approve uploads) — never per-experiment values. Every change appends a `## History` line.
- Experiment `experiment_state.md` never duplicates the workspace inputs: no `Project` / `Location` / `Auto-approve uploads` / `Enrichment sources` bullets except the explicit `(this experiment)` overrides from the review step. Identity is carried by the resource names (`Final Context Set resource`, `Draft Context Set resource`, `Seed Context Set resource`).
- Each experiment's `experiment_state.md` records the `tools.yaml` source and tools it uses (`## Active Database`); downstream skills take the source from there, never by guessing from `tools.yaml`.
- A finished experiment (`## Final:` in `experiment_state.md`) is read-only: never change its `dataset/` or `experiment_state.md`; clone it instead.
- Do not guess DB connection details. Ask the user for every required field explicitly.

## Credentials message (use when collecting DB info for `tools.yaml`)

> "I'll help you configure the database connection in `tools.yaml`. The Toolbox server uses Application Default Credentials (ADC) for authentication, so you don't need to provide a username or password. **Strongly recommended:** use a **read-only** database principal / IAM role.
>
> Could you please provide the following details:
> - Google Cloud Project ID:
> - Region: (or Instance ID / Database ID for Spanner)
> - Dialect: (for Spanner: GoogleSQL [default] or PostgreSQL)
> - Target tables or property graphs to focus on (optional):
> - ... (other required fields based on database type)"

## References
- `references/<db_type>.md` — per-DB required fields and YAML template: [AlloyDB Postgres](references/alloydb-postgres.md), [BigQuery](references/bigquery.md), [Cloud Bigtable](references/cloud-bigtable.md), [Cloud SQL MySQL](references/cloud-sql-mysql.md), [Cloud SQL Postgres](references/cloud-sql-postgres.md), [Firestore (MongoDB API)](references/firestore.md), [Spanner GoogleSQL](references/spanner-googlesql.md), [Spanner PostgreSQL](references/spanner-postgresql.md), [Custom / Pluggable Engine](references/custom-engine.md).

## Gotchas
- **Quota project vs ADC project:** ADC infers a default project from `gcloud config`, but Context Set server requires an explicit quota project via `X-Goog-User-Project`. Missing quota project → 400 from Context Set API.
- **Context Set uploads and deletes are asynchronous:** `upload_context_set` / `delete_context_set` return an operation, not a finished result. Downstream skills must poll `get_operation(projectId, location, operationId)` until `done: true`, waiting ≥5 s between polls (see the Context Set MCP Protocol in `context-engineering-workflow`). The preflight probe above uses `get_context_set`, which is synchronous, precisely so it needs no polling.
- **Context Set endpoint lives in the plugin manifests, not in `tools.yaml`:** the remote server URL is the `ctxset` entry in `plugin/mcp_config.json` / `gemini-extension.json`. A probe that fails with a connection or DNS error points at that URL or at the client's MCP configuration, not at the user's `tools.yaml`. The client mints the bearer token from ADC and sets `X-Goog-User-Project` from the ADC quota project, which is why the quota-project check above matters.
- **MCP restart required whenever `tools.yaml` changes — by this skill or by the user:** the `toolbox` MCP server reads `.context-engineering/tools.yaml` only at startup. Standalone validation (`uvx toolbox-server … invoke`) sees the new file immediately, which makes the stale server easy to miss. Symptoms: a source that is in `tools.yaml` has no `<source>-list-schemas` tool, or a tool still reflects a connection value that the user has since edited. Fix: restart the `toolbox` server with the per-client instructions above, then re-run the *Toolbox server in sync* check.
- **AlloyDB requires `cluster` + `instance`; Cloud SQL only `instance`.**
- **Spanner uses ADC; verification fails without `gcloud auth application-default login`.**
- **Evalbench cold-cache:** first `uvx google-evalbench@1.18.0` can take minutes to download; verifying `Evalbench reachable` warms the cache so downstream `evaluate` runs are fast.
