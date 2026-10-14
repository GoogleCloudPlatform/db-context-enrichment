---
name: context-engineering-evaluate
description: Guides the agent to execute an evaluation of a ContextSet against a golden NLQ+SQL dataset using the Evalbench framework, either standalone or as one iteration of the hill-climbing loop.
---

> **Load [`context-engineering-workflow`](../context-engineering-workflow/SKILL.md) first** for shared terminology, the Context Set (OneMCP) Protocol, and safety protocol.

# Skill: Evaluation Scoring

## Goal
Score a ContextSet against a dataset by running Evalbench, and return a scored result — overall accuracy, raw `passed` / `total` counts, the report directory, plus dominant failure categories.

> [!IMPORTANT]
> **Evaluate is a pure function over its inputs.** It reads whatever the caller hands it, writes only under the caller's `output_dir`, and **never modifies `experiment_state.md`**. The caller (hillclimb, the holdout step, or the user) records the returned numbers. This keeps one writer per field and lets evaluate be used on any file or resource without side effects on an experiment.


## Prerequisites

### Inside an experiment (called by hillclimb or the holdout step, or by the user on an existing experiment)

Read `.context-engineering/experiments/<experiment_name>/hillclimb/experiment_state.md` and take:

| Input | From |
| :--- | :--- |
| Toolbox source | `## Active Database` → **Source Name** (must exist in the shared `.context-engineering/tools.yaml`, which is the `toolbox_config_path` passed to `generate_evalbench_configs`). If its `<source>-*` tools are not visible, the `toolbox` MCP server is stale — tell the user to restart it (see `context-engineering-init`). |
| Dataset | `Hillclimb dataset` by default; `Holdout dataset` **only** when the caller is the holdout step; `Golden dataset` only if the user explicitly asks for a full-set score. All three live under `<experiment>/dataset/`. Never offer the holdout split as a casual choice — it must stay unseen during optimization. |
| ContextSet resource | The caller names it: the working copy during the loop and for the holdout step (the bare `<context_set_id>` in the fresh case, `<context_set_id>_draft` in the existing case — per `Draft Context Set resource` in `experiment_state.md`), or a resource the user names. |
| `output_dir` | Supplied by the caller: `<experiment>/hillclimb/vN/eval/` during the loop, `<experiment>/hillclimb/holdout_eval/` for the holdout step. |
| GCP project / location | Parsed from the resource name above (Resource naming rule) — never from `workspace_state.md`, which only seeds init. |

If there is no `experiment_state.md` for the experiment the user is talking about, route to [context-engineering-init](../context-engineering-init/SKILL.md) rather than collecting the values inline. If `experiment_state.md` contains `## Generalizability`, the experiment is finished: evaluating its published resource read-only is fine, but never upload into it.

### Standalone (no experiment)

Ask only for what is missing:

- A working DB connection (`tools.yaml` configured for the Toolbox MCP server — see `context-engineering-init` if missing).
- ADC configured and the Gemini Data Analytics + Dataplex APIs enabled on the project (see `context-engineering-init` for preflight).
- A dataset (absolute path) in the **simplified user-facing format** — a JSON list of objects, each with:
  - `id`: unique identifier (e.g., `eval_001`).
  - `database`: target database name.
  - `nlq`: natural language question.
  - `golden_sql`: correct reference SQL query.

  Example:
  ```json
  [
    {
      "id": "eval_001",
      "database": "my_db",
      "nlq": "Count users",
      "golden_sql": "SELECT COUNT(*) FROM users"
    }
  ]
  ```
- A ContextSet, supplied as **exactly one of**:
  - **A full Context Set resource name** (shape per the **Resource naming rule** in `context-engineering-workflow`). Used directly.
  - **A local ContextSet JSON file.** QueryData can only use a context set that exists on the Context Set server, so the file must be uploaded first — see step 2.
- An `output_dir` (absolute or workspace-relative) where the eval configs and reports should live. If the user hasn't specified one, suggest `./eval-runs/<name>/`.

## Guidance

1. **Collect inputs** per the applicable Prerequisites table. Trust `tools.yaml` values as-is — don't ask the user to re-verify them.

2. **Prepare the ContextSet resource name.**
   - A resource name is used directly: parse it per the Resource naming rule (`projectId` after `projects`, `location` after `locations`, `contextSetId` = last segment; **accept any collection segment** — `contextSets`, `entryGroups`, …), optionally confirm it exists with `get_context_set(projectId, location, contextSetId)`, and pass the **unchanged string** to `generate_evalbench_configs(context_set_id=…)` in step 4.
   - For a **local file**:
     - Say plainly: *"This local file must be pushed to GCP to run evaluation. May I upload it?"* and name the target.
     - **Inside an experiment** the target is the **working copy** per `experiment_state.md`: the bare `<context_set_id>` (`Final Context Set resource`) when `Draft Context Set resource` is `(none …)` — a fresh context set — otherwise the `Draft Context Set resource` (`<context_set_id>_draft`). If `Auto-approve uploads` is `true` the question above is informational and you proceed, otherwise wait for approval. Never write to an *existing* context set's bare id from evaluate — that only happens in hillclimb's Finalize HITL.
     - **Standalone** take `projectId` and `location` from `.context-engineering/workspace_state.md` when it exists (show them; ask only if missing or the user wants different ones), ask for a `contextSetId` (do not guess); call `list_context_set_locations(projectId)` and make sure `location` is in the list; show the exact resource name; warn that if a context set with this name already exists the upload **overwrites it** irrecoverably; proceed only on explicit consent.
     - Run `validate_context_set` on the file first; then read the file and call `upload_context_set(projectId=<project_id>, location=<location>, contextSetId=<context_set_id>, contextPayload=<exact file contents>, databases=<Database>)` — the three identity parts come from the resource name above (`contextSetId` is its last path segment; inside an experiment, the working copy's id); `<Database>` is derived from the `## Active Database` **Source Name** in `experiment_state.md` (standalone: the selected source) and that source's block in `tools.yaml`, per the *Database association* table in `context-engineering-workflow`, sent in the wire shape the live schema accepts (object list or URI-string list — see that section). There is no file-path argument.
     - Poll `get_operation(projectId, location, operationId)` on the returned operation (≥5 s between polls, 5-minute ceiling), logging each response, until `done: true` — see the Context Set (OneMCP) Protocol in `context-engineering-workflow`. **Do not call `generate_evalbench_configs` until `done: true` is observed**; evaluating before the upload has landed scores a missing or stale context set.
     - On an operation that reports an `error`, surface it verbatim and stop.

3. **Select the DB source.** Inside an experiment it is the **Source Name** under `## Active Database` in `experiment_state.md` (confirm it still exists in the shared `.context-engineering/tools.yaml`; if not, stop and ask the user to restore it or re-run `context-engineering-init`). Standalone: find all `kind: source` blocks in `.context-engineering/tools.yaml` whose `type` is a supported evaluation engine (consult `generate_evalbench_configs` for the current list); auto-select if exactly one, otherwise list `name` + `type` and let the user pick.

4. **Generate the Evalbench configs.** Call `generate_evalbench_configs(output_dir, dataset_path, context_set_id=<resource>, toolbox_config_path=.context-engineering/tools.yaml, toolbox_source_name=<source>)`. The tool writes configs under `<output_dir>/eval_configs/`. This is the only supported way to produce Evalbench configs — never author them by hand.

5. **Run Evalbench.**
   - **Environment variables**: ensure the required GCP environment variables are exported:
     ```bash
     export EVAL_GCP_PROJECT_ID="<project_id>"
     export EVAL_GCP_PROJECT_REGION="global"
     ```
   - Shell out from the caller's cwd: `uvx google-evalbench@1.18.0 --experiment_config=<output_dir>/eval_configs/run_config.yaml`
   - Reports materialize under `<output_dir>/eval_reports/<job_id>/` (the `job_id` appears in the tool's stdout). The run can take many minutes for larger datasets — let it complete; do not kill or restart on apparent stalls. Treat a non-zero exit code as a hard failure and surface stderr verbatim.

6. **Read and return results.** Call `read_evaluation_result` on `<output_dir>/eval_reports/<job_id>/`. Return to the caller:
   ```
   {passed, total, accuracy, job_id, eval_dir: "<output_dir>/eval_reports/<job_id>/"}
   ```
   plus the dominant failure categories and the absolute path to the full reports.
   - **Standalone**: present these in chat and suggest hillclimb as the natural next step if the user wants to iteratively improve.
   - **Inside the loop**: hand the numbers back to hillclimb; it decides what to say and writes `experiment_state.md`. The workflow's *Master Loop Control* supersedes any "next steps" summary here.

7. **Handling QueryData API errors**: if the evaluation results or failure cases show an API error under `SQL Generator Error`:
   1. Distinguish this from a context/prompt quality defect.
   2. Inform the user that the evaluation encountered an API error and advise them on how to fix it. These errors must be fixed before the results are usable; **do not record the score** of such a run as an iteration result.
   3. For errors related to API field access, advise the caller to verify API field visibility: "Your request references pre-release or private preview feature. Please ensure your GCP project is allowlisted for access by contacting your Google Cloud account team."

## Rules

- Never write `experiment_state.md`. Return results; the caller records them.
- Never evaluate a context set whose upload operation has not reported `done: true`.
- Inside an experiment, evaluate's only upload target is the working copy recorded in `experiment_state.md`; never write to an existing context set's bare id.
- Never pick the holdout split on your own initiative; it is used once, by the holdout step, after the hill-climb loop has converged.
- Never invoke bootstrap or hillclimb from within this skill.
- If both a resource name and a local file are provided, ask the user which to use — do not silently pick.
- On `generate_evalbench_configs` errors, surface the error and stop; do not retry blindly.
- Standalone, use the caller's Context Set coordinates verbatim; if any are missing, ask explicitly — do not infer from filenames, paths, or `tools.yaml` without confirmation.

## Tools

**MCP:**
- `validate_context_set` — check a local file before uploading it.
- `list_context_set_locations` (remote Context Set server) — confirm the upload location; standalone local-file path only.
- `upload_context_set` (remote Context Set server) — used only when the caller supplies a local file instead of a resource name; takes the file contents inline in `contextPayload`; returns an operation.
- `get_operation` (remote Context Set server) — poll the upload operation until `done: true` before evaluating.
- `generate_evalbench_configs` — produces Evalbench YAML configs on disk.
- `read_evaluation_result` — parses `scores.csv` / `summary.csv` into a markdown summary.

**Shell:**
- `uvx google-evalbench@1.18.0 --experiment_config=<path>` — runs the eval job against the published release.

**References:**
- `references/<db_type>.md` — per-engine schema examples for fixing `tools.yaml` source blocks if `generate_evalbench_configs` reports a validation failure, and the extra `experiment_state.md` inputs some engines need: [AlloyDB Postgres](references/alloydb-postgres.md), [BigQuery](references/bigquery.md) (`Table Ids`), [Cloud Bigtable](references/cloud-bigtable.md), [Cloud SQL MySQL](references/cloud-sql-mysql.md), [Cloud SQL Postgres](references/cloud-sql-postgres.md), [Spanner GoogleSQL](references/spanner-googlesql.md) (`Graph Ids`), [Spanner PostgreSQL](references/spanner-postgresql.md), [Custom / Pluggable Engine](references/custom-engine.md).
