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
1. Identify the DB type. The supported databases are: Cloud SQL Postgres, Cloud SQL MySQL, AlloyDB Postgres, Spanner GoogleSQL (Graph supported), Spanner PostgreSQL (no Graph support), Cloud Bigtable, Firestore (MongoDB API), BigQuery, and Custom / Pluggable Engine (`type: custom`). Load the corresponding `references/<db_type>.md` for required fields. **Spanner dialect disambiguation rule**: if the user says "Spanner" without specifying the dialect (`GoogleSQL` vs `PostgreSQL`), ask the user for the dialect alongside the connection details in step 2 (or, **only if** the user has already explicitly provided `<project_id>`, `<instance_id>`, and `<database_name>` in their message, run `gcloud spanner databases describe <database_name> --instance=<instance_id> --project=<project_id> --format="value(databaseDialect)"` — `GOOGLE_STANDARD_SQL` → `spanner-googlesql.md`; `POSTGRESQL` → `spanner-postgresql.md`). Never run `gcloud spanner instances list` or `gcloud spanner databases list` to search for or guess `<instance_id>` or `<database_name>`.
2. Ask the user for every required field explicitly (do not fill in missing values or extract unconfirmed connection details from design docs).
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

**Toolbox restart & tool naming rule (always state the restart rule explicitly).** The `toolbox` MCP server only reads `tools.yaml` when it starts, so the agent's `<source>-*` tools do not change until it is restarted. *(Common naming rule: across all context-engineering skills, `<source>-list-schemas` and `<source>-execute-sql` denote a source's schema and query tools — for SQL/BTQL sources these are `<source>-list-schemas` and `<source>-execute-sql` [plus `<source>-list-graphs` for Spanner Graph], and for Firestore they are `<source>-get-schema` and `<source>-execute-mql`.)* Tell the user to restart `toolbox`:
- after **every** write this skill makes to `tools.yaml`;
- whenever the user says they edited `tools.yaml` themselves;
- whenever a source listed in `tools.yaml` has no matching `<source>-list-schemas` / `<source>-execute-sql` (or Firestore `<source>-get-schema` / `<source>-execute-mql`) tool in the agent's tool list (the tell-tale sign of a stale server).

Restart instructions per client:
- Gemini CLI: `/mcp reload`
- Claude Code: `/mcp` → `toolbox` → Reconnect (or `/quit` and relaunch). *(Note: On the very first run on a machine with a cold `uvx` cache, `uvx toolbox-server@1.14.0` downloads a ~40 MiB binary, which can take longer than 30s and hit Claude Code's 30s MCP connection timeout (`connection timed out after 30000ms`). If the timeout still occurs during `/mcp` → Reconnect, simply click **Reconnect** a second time — and the binary should be cached and connected.)*
- Antigravity CLI: `/mcp` → `toolbox` → Restart. *(Note: Because Antigravity starts plugin MCP servers inside `~/.gemini/config/plugins/<plugin>/` rather than the workspace directory, before asking the user to restart `toolbox` — and whenever checking `tools.yaml` in preflight — if `~/.gemini/config/plugins/db-context-engineering` or `~/.gemini/config/plugins/db-context-engineering-dev` exists, ensure `"<absolute_workspace_path>/.context-engineering"` exists (`mkdir -p`), remove `~/.gemini/config/plugins/<matched_plugin_name>/.context-engineering` first only if it is a real directory rather than a symlink (`[ -d ... ] && [ ! -L ... ]`), and symlink it to the active workspace via `ln -sfn "<absolute_workspace_path>/.context-engineering" ~/.gemini/config/plugins/<matched_plugin_name>/.context-engineering` (ensuring the workspace path is fully resolved to an absolute path) so `uvx` resolves `.context-engineering/tools.yaml` to the current workspace immediately on `/mcp` → Restart.)*

### Record the workspace inputs (`workspace_state.md`)

Run this when `.context-engineering/workspace_state.md` is missing (first experiment in a workspace) or when the user asks to change a default. Everything here is asked **once per workspace**; downstream skills read the answers from the file and never re-ask.

1. **DB connection** — if `.context-engineering/tools.yaml` does not exist, run **Create new** above first (and give the restart reminder).
2. **Project** — the GCP project id the context sets are published in (default: ADC's project). At the same time check the **ADC quota project** (`quota_project_id` in `~/.config/gcloud/application_default_credentials.json`): if missing, stop and give the fix (`gcloud auth application-default set-quota-project <project>`); if it differs from `<project>`, tell the user that API calls are billed/authorized against `<quota>` while context sets live in `<project>`, and continue only if they confirm that is intended. The quota project is **not** recorded in the file.
3. **Location (Context Set location)** — the GCP location where the Context Set is stored. Call `list_context_set_locations(projectId)` and ask, naming the purpose: *"Which location should be used for storing your context sets? Available: `<list>`."* If the user already named one, confirm it is in the list. Do not assume a default.
4. **Default DB source** — the `tools.yaml` source experiments use by default. One source in `tools.yaml` → record it **without asking**. Several → ask which one. (When a source is added later through **Add to existing**, ask whether it should become the default.)
5. **Enrichment sources** (optional) — material about the database that helps both the **evaluation dataset** (realistic questions) and the **initial context set** (business terms, join rules). Ask in plain words, no skill names: *"Do you have any design docs, application code, sample SQL queries or notes about this database that I should read when creating the evaluation questions and the initial context set? Share file paths, or say none."* Record the list, or `(none)`.
6. **Upload approval** — **always ask, never infer.** Ask once, verbatim and neutrally — no "recommended", "default" or any steer attached to either option: *"Improving the context set takes several rounds, and each round's draft version is uploaded to the Context Set server to be scored. Should I upload these draft iterations automatically, or pause for your approval before each upload to review the ContextSet manually first?"* Record `Auto-approve uploads: true` **only** when the user's answer to *this question* chooses automatic (e.g. "upload automatically", "auto-approve", "run unattended"). Everything else records `false` — no answer, an unsure answer, or any prompt wording that merely authorises a *specific* upload ("upload it once", "upload the baseline", "upload and poll to done"): that is consent for that one action, not a standing preference, and it does **not** replace the question. The `false` fallback is an internal safety rule, not something to present to the user as advice. Do not add caveats about end-of-run replacement here — that HITL is explained when it is relevant (existence probe, step 3 of the experiment flow).

Write the file in the format shown in `context-engineering-hillclimb/references/layout.md` and read the recorded values back in one short summary. **Only this skill writes `workspace_state.md`.** Every later change (a default the user asks to change, a new Default DB source) rewrites the bullet and appends one line under `## History` (`- **Updated**: <date> — <what changed>`).

### Initialise the experiment `experiment_state.md`

Run this when a user is starting a hill-climb experiment, or when a downstream skill routes here because `.context-engineering/experiments/<experiment_name>/hillclimb/experiment_state.md` is missing or incomplete. If `workspace_state.md` is missing, run **Record the workspace inputs** first. Everything below is asked **once**; downstream skills (`dataset-generation`, `bootstrap`, `hillclimb`, `evaluate`, `workflow`) read the answers from `experiment_state.md` and never re-ask. If the file already exists, only fill in the missing bullets — do not overwrite existing values or any `## Iteration Log`. If the file already contains `## Final:`, the experiment is **finished**: do not modify it; offer the clone flow in [references/clone-and-existing-modes.md](references/clone-and-existing-modes.md) instead.

- **Pre-step modes (`workspace_state.md` review, Clone mode, or Existing-context-set mode):** If `.context-engineering/workspace_state.md` already existed from an earlier setup (not just created in this turn), OR if the user is **cloning a finished experiment** (*"cloned from `<source>`"*), OR if the user is **improving an already-published Context Set** (*"improve / fix `projects/<p>/locations/<l>/<collection>/<id>`"*), **load [references/clone-and-existing-modes.md](references/clone-and-existing-modes.md)** and execute the applicable pre-step instructions before step 1 below.

1. **Experiment name** — ask for a short slug (e.g. `retail-graph`). The experiment root is `.context-engineering/experiments/<experiment_name>/`; create it together with its `hillclimb/` sub-directory (`dataset/` is created by dataset-generation, or now if a golden set is being copied in). `experiment_state.md` is written at `<experiment_root>/hillclimb/experiment_state.md`.
2. **Context set id** — the name the **final** context set is published under. Default: the experiment name. Derive `Final Context Set resource` strictly per the **Resource naming rule** in `context-engineering-workflow` from `workspace_state.md`'s `Project` / `Location` (verbatim user string when one was supplied) — do not hardcode a path shape here.
3. **Existence probe → working-copy strategy.** Probe the bare id with `get_context_set(projectId=<project>, location=<location>, contextSetId=<context_set_id>)` and record the result as the `Draft Context Set resource` bullet; this single bullet tells hillclimb how to work:
   - **NOT_FOUND (fresh context set — including plain text `"Resource was not found."` with `isError: true`)** → do not probe other locations; record `Draft Context Set resource: (none — new context set; iterations upload to the final name)`. Tell the user explicitly naming `<location>`: *"Context set `<context_set_id>` does not exist in location `<location>` (`<Final Context Set resource>`), so I'll build it in place: every iteration is uploaded under that name and the best one stays there at the end. No scratch copy, nothing to delete."*
   - **Exists** → record `Draft Context Set resource: <Final Context Set resource with its last segment replaced by <context_set_id>_draft>` (same collection segment), warn the user that iterations go to `<Draft Context Set resource>` while `<Final Context Set resource>` stays untouched until the end-of-run replacement HITL (after which the draft is deleted), and if they did not supply this resource as their seed, offer to pick a different `Context set id` (see [references/clone-and-existing-modes.md](references/clone-and-existing-modes.md) for the exact warning text).
4. **Seed Context Set resource** (optional; pre-filled in clone and existing-context-set modes) — an existing Context Set resource name to start from, recorded **verbatim** as `Seed Context Set resource: <resource name>` (parsed per the Resource naming rule; any collection segment accepted). Hillclimb downloads it once as `v0` and never writes to it during the loop. Otherwise record `Seed Context Set resource: (none — seeded from bootstrap)` or `Seed Context Set resource: (local file: <path>)`.
5. **Active database** — the `tools.yaml` source this experiment targets (the `Default DB source` from `workspace_state.md`, or the one chosen in the review step). Confirm its `<source>-list-schemas` (or Firestore `<source>-get-schema`) tool is visible in your tool list (if not, apply the Toolbox restart rule above first) and that the `tools.yaml` block has all required connection fields for its engine. Record under `## Active Database`: **Config** (`./.context-engineering/tools.yaml`), **Source Name**, **Type**, and **Tools** (e.g. `financial-list-schemas, financial-execute-sql`), plus engine-specific scope bullets read by `generate_evalbench_configs` (Spanner GoogleSQL: `- **Graph Ids**: [...]` from `<source>-list-graphs`; BigQuery: `- **Table Ids**: [...]` from `<source>-list-schemas`; optional `- **Table Ids**: [...]` for Bigtable/Firestore — see [references/clone-and-existing-modes.md](references/clone-and-existing-modes.md)).
6. **Existing dataset** — the only dataset file a user (or a clone) can bring in is `.context-engineering/experiments/<experiment_name>/dataset/golden.json`. If the user has their own dataset, offer to copy it there and record `Golden dataset: <path> (user-supplied; expand before split)`. If no file is present, omit the dataset bullets. **Never record `Hillclimb dataset` / `Holdout dataset` here** — `dataset/splits/` is produced exclusively by `context-engineering-dataset-generation` via `split_dataset`; reject pre-split `dev.json` / `test.json` or hand-made `splits/` files.

Write the file in the format shown in `context-engineering-hillclimb/references/layout.md` (a `## Metadata` section with the bullets above, then `## Active Database`). Confirm the path and the recorded values back to the user in one short summary.

### Verify environment (broad or scoped)

**Load [references/environment-checks.md](references/environment-checks.md)** when running broad verification ("am I ready?"), verifying preflight readiness (`uv`, Evalbench, ADC + quota project, Dataplex/GDA APIs, `ctxset` MCP connection & `get_context_set` access probe, `tools.yaml` & Antigravity symlink check, `workspace_state.md` & `list_context_set_locations(Project)` check, Toolbox server sync, DB source reachability), or diagnosing a downstream failure. Report `PASS` or `FAIL` per check, and ask the user for consent before executing anything mutating (installing packages, enabling APIs, changing IAM, writing files).

## Rules
- Never execute mutating actions (`gcloud services enable`, `gcloud projects add-iam-policy-binding`, package installs, file writes) without explicit user consent — surface the exact command and let the user run it, or ask consent before running.
- ADC only for DB auth. Never write username/password into `tools.yaml`. Strongly recommend a **read-only** database principal / IAM role. Do not guess DB connection details — ask the user for every required field explicitly.
- `tools.yaml` always lives at `.context-engineering/tools.yaml` (one shared file per workspace; never copy it into an experiment). If it exists, ask whether to append or overwrite. Every write ends with the Toolbox restart reminder.
- `workspace_state.md` always lives at `.context-engineering/workspace_state.md` and is written **only by this skill** (workspace inputs only; every change appends a `## History` line).
- Experiment `experiment_state.md` never duplicates workspace inputs (except explicit `(this experiment)` overrides from the review step); identity is carried by `Final Context Set resource`, `Draft Context Set resource`, and `Seed Context Set resource`, and `## Active Database` records the target `tools.yaml` source and tools. A finished experiment (`## Final:`) is read-only — clone it instead.

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
- [Clone & Existing-Context-Set Modes](references/clone-and-existing-modes.md) — reviewing existing `workspace_state.md` inputs, cloning finished experiments, and improving published Context Sets.
- [Environment Checks & Gotchas](references/environment-checks.md) — preflight verification checks (`uv`, Evalbench, ADC/quota project, APIs, IAM probes, workspace files) and troubleshooting gotchas.
- `references/<db_type>.md` — per-DB required fields and YAML template: [AlloyDB Postgres](references/alloydb-postgres.md), [BigQuery](references/bigquery.md), [Cloud Bigtable](references/cloud-bigtable.md), [Cloud SQL MySQL](references/cloud-sql-mysql.md), [Cloud SQL Postgres](references/cloud-sql-postgres.md), [Firestore (MongoDB API)](references/firestore.md), [Spanner GoogleSQL](references/spanner-googlesql.md), [Spanner PostgreSQL](references/spanner-postgresql.md), [Custom / Pluggable Engine](references/custom-engine.md).
