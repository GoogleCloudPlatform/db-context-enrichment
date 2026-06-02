---
name: skill-evaluate
description: Runs an Evalbench evaluation of a ContextSet against a golden NL2SQL dataset. Either generates the Evalbench run configuration from minimum inputs, or executes a user-supplied run_config.yaml directly.
---

# Evaluation Workflow

This skill performs a single evaluation run using Google's Evalbench framework. It is standalone — it does **not** read or write `autoctx/`, `state.md`, or any experiment folder. All paths are inputs, supplied either by the user (when invoked directly) or by an orchestrating caller (e.g., `skill-hillclimb`).

The skill supports two modes:

- **Generate-and-run** (minimum inputs): the skill generates a fresh Evalbench run configuration from the minimum required information and then executes Evalbench against it.
- **Run-existing** (pre-existing config): the user already has a valid Evalbench `run_config.yaml`; the skill skips generation and just runs Evalbench against it.

## Input

Required, depending on the mode:

**Generate-and-run mode:**
- `tools_config_path`: absolute path to a `tools.yaml` containing the target database connection.
- `toolbox_source_name`: the `name` of the `kind: source` block within `tools.yaml` to evaluate against. If omitted and only one supported source exists, auto-select it.
- `context_set_id`: the Data Agent's authored context configuration identifier, e.g., `projects/<project_id>/locations/<region>/contextSets/<context_set_name>`. Retrievable from the GCP Database Studio console.
- `dataset_path`: absolute path to the golden evaluation dataset, in the **simplified user-facing format** (see "Dataset Format" below).
- `output_dir`: absolute path to the directory where generated configs and reports will be written. This is **required** — do not default it.

**Run-existing mode:**
- `run_config_path`: absolute path to a pre-existing Evalbench `run_config.yaml`.

## Workflow

1. **Determine mode.**
   - If the caller has supplied `run_config_path`, use **run-existing** mode.
   - If the caller has supplied minimum-info inputs, use **generate-and-run** mode.
   - If the skill was invoked directly with no inputs pre-supplied, ask the user which mode they want and collect the appropriate inputs.

2. **Run-existing mode — Validate.**
   - Verify the `run_config_path` file exists. If not, STOP and report the missing path.
   - Skip to step 4.

3. **Generate-and-run mode — Collect inputs and generate configs.**
   - Collect any missing inputs from the user. Do **not** ask the user to explain or verify the database configuration beyond selecting the source.
   - **Source selection:** read `tools_config_path` to enumerate `kind: source` blocks with supported evaluation engines (consult the `generate_evalbench_configs` tool description for the exact list). If `toolbox_source_name` was not provided:
     - If exactly one supported source exists, auto-select it and inform the user.
     - If multiple exist, list `name` and `type` and ask the user to choose.
   - **Generate configs:** call the `generate_evalbench_configs` MCP tool with `dataset_path`, `context_set_id`, `tools_config_path`, `toolbox_source_name`, and `output_dir`. This is the **only** way to generate Evalbench configs — never invent them from scratch.
   - The tool writes `run_config.yaml`, `db_config.yaml`, `model_config.yaml`, `llmrater_config.yaml`, and `golden_queries.json` (the simplified dataset converted to the Evalbench-internal format) into `output_dir`.
   - If the tool fails, analyze the error and retry with corrected inputs. If it is an internal system error, STOP and inform the user.
   - Set `run_config_path = <output_dir>/run_config.yaml` for step 4.

4. **Run Evalbench.**
   - Trigger `run_shell_command` to execute:
     `uvx google-evalbench --experiment_config=<run_config_path>`
   - Check the command output to confirm the run succeeded and that report files materialized at the location specified by the run config's `output_dir` setting.

5. **Report results.**
   - Tell the user (or return to the caller) the location of the generated configs (if generate-and-run mode) and the location of the evaluation reports.
   - Share top-level performance metrics from `summary.csv` if available.

## Dataset Format

The skill expects the golden dataset in the **simplified user-facing format**: a JSON list of objects, where each object has:
- `id`: unique string identifier (e.g., `eval_001`).
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

The `generate_evalbench_configs` tool converts this into the Evalbench-internal `golden_queries.json` format automatically; the user never needs to author Evalbench-format datasets directly.

## Output

Upon successful completion:

- **Generate-and-run mode:** `output_dir` contains `run_config.yaml`, `db_config.yaml`, `model_config.yaml`, `llmrater_config.yaml`, `golden_queries.json`, plus the Evalbench report folder.
- **Run-existing mode:** the Evalbench report folder materializes at the location specified in the supplied `run_config.yaml`.

## Templates & Reference

When listing sources from `tools.yaml`, only present `kind: source` records. The `generate_evalbench_configs` tool validates the selected block's connection parameters deterministically. If the tool reports a verification failure for a specific database type, refer to the schema examples inside `references/` (e.g., `cloud-sql-postgres.md`) to guide the user on fixing their `tools.yaml` definition.
