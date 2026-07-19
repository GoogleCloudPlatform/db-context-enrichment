---
name: context-engineering-evaluate
description: Guides the agent to execute an evaluation of a ContextSet against a golden NLQ+SQL dataset using the Evalbench framework.
---

> **Load [`context-engineering-workflow`](../context-engineering-workflow/SKILL.md) first** for shared terminology, lifecycle overview, and safety protocol.

# Skill: Evaluation Scoring

## Goal
Score a ContextSet against a golden dataset by running Evalbench, and return a scored report — overall accuracy plus dominant failure categories.

## Prerequisites

- A working DB connection (`tools.yaml` configured for the Toolbox MCP server — see `context-engineering-init` if missing).
- ADC configured and the Gemini Data Analytics + Dataplex APIs enabled on the project (see `context-engineering-init` for preflight).
- A golden evaluation dataset (absolute path) in the **simplified user-facing format** — a JSON list of objects, each with:
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
  - **`cs_resource_name`** — a full Context Store resource name (e.g., `projects/<p>/locations/<l>/contextSetGroups/<g>/contextSets/<c>@<v>`). Used directly.
  - **Local ContextSet JSON file** + the coordinates required by `upload_context_set` — the skill uploads it (with explicit user consent) to obtain a `cs_resource_name` for the run.

- An `output_dir` (absolute or workspace-relative) where the eval configs and reports should live. If the user hasn't specified one, prompt them; a sensible suggestion is `./eval-runs/<name>/`.

## Guidance

1. **Collect inputs.** Prompt only for what's missing from the Prerequisites. Trust `tools.yaml` values as-is — don't ask the user to re-verify them.

2. **Prepare the ContextSet resource name.**
   - If the user supplied a `cs_resource_name`, use it directly.
   - If the user supplied a local file:
     - Confirm every field required by `upload_context_set` is present. Ask for any missing values individually — do not guess.
     - Ask for explicit consent before uploading. Summarize the target resource in the prompt so the user knows what will be written.
     - On consent, call `upload_context_set`. The returned resource name becomes `cs_resource_name` for the rest of this run.
     - On `upload_context_set` failure, surface the error verbatim and stop. Do not fall back to a manual upload URL.

3. **Select the DB source from `tools.yaml`.**
   - Find all `kind: source` blocks whose `type` is a supported evaluation engine (consult `generate_evalbench_configs` for the current list).
   - If exactly one supported source exists, inform the user and auto-select it.
   - If multiple, list their `name` + `type` and let the user pick.

4. **Generate the Evalbench configs.** Call `generate_evalbench_configs`. The tool writes configs under `<output_dir>/eval_configs/`. This is the only supported way to produce Evalbench configs — never author them by hand.

5. **Run Evalbench.** Shell out from the caller's cwd:
   `uvx google-evalbench@1.10.0 --experiment_config=<output_dir>/eval_configs/run_config.yaml`
   Reports materialize under `<output_dir>/eval_reports/<job_id>/` (the job_id appears in the tool's stdout). The run can take many minutes for larger datasets — let it complete; do not kill or restart on apparent stalls. Treat a non-zero exit code as a hard failure and surface stderr verbatim.

6. **Read and summarize results.** Call `read_evaluation_result` on the run folder `<output_dir>/eval_reports/<job_id>/`. Report to the user: overall score, dominant failure categories, and the absolute path to the full reports. Suggest hillclimb as a natural next step if the user wants to iteratively improve.

## Rules

- Never upload a ContextSet without explicit user consent.
- Never invoke bootstrap or hillclimb from within this skill.
- If both `cs_resource_name` and a local file are provided, ask the user which to use — do not silently pick.
- On `generate_evalbench_configs` errors, surface the error and stop; do not retry blindly.
- This skill is stateless. Every path comes from the caller — do not assume a workspace layout or write cross-phase state files.
- Use the caller's Context Store coordinates (`project_id`, `csg_id`, `cs_id`, `version`) verbatim when supplied. If any are missing, ask the user explicitly — do not infer from filenames, paths, or `tools.yaml` without their confirmation.

## Tools

**MCP:**
- `upload_context_set` → `cs_resource_name` — used only when the caller supplies a local file instead of a resource name.
- `generate_evalbench_configs` — produces Evalbench YAML configs on disk.
- `read_evaluation_result` — parses `scores.csv` / `summary.csv` into a markdown summary.

**Shell:**
- `uvx google-evalbench@1.10.0 --experiment_config=<path>` — runs the eval job against the published release.

**References:**
- `references/<db_type>.md` (`alloydb-postgres.md`, `cloud-sql-mysql.md`, `cloud-sql-postgres.md`, `spanner.md`) — per-engine schema examples for fixing `tools.yaml` source blocks if `generate_evalbench_configs` reports a validation failure.
