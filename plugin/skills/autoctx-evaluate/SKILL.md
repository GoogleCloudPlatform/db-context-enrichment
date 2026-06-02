---
name: skill-autoctx-evaluate
description: Run EvalBench against any uploaded ContextSet on any configured database. Standalone; no workspace assumptions, no `state.md` writes.
---

# Auto Context Evaluation

## Goals

Run EvalBench for a `(context_set_id, golden dataset, DB source)` triple and produce a scored report directory. Surface the score and report path to the caller.

## Prerequisites

- `context_set_id` — a full Context Store resource name (eg. `projects/.../contextSets/<name>@<version>`). The user obtains it from a prior `upload_context_set` call or supplies it directly. If they only have a local ContextSet file, tell them to upload it first via the `upload_context_set` MCP tool, then re-invoke this skill.
- Golden dataset path — absolute path to a JSON file in the **simplified user-facing format** (see below).
- `tools.yaml` path + Toolbox source name — DB connection details are looked up from the named source entry. If `tools.yaml` is missing, refer the user to `skill-autoctx-init`.

**Simplified golden dataset format:**

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

Keys: `id`, `database`, `nlq`, `golden_sql`. The tool converts this to EvalBench's internal format automatically.

## Guidances

1. **Collect inputs.** Ask the user for any of `context_set_id`, golden dataset path, `tools.yaml` path, source name that they have not already provided. Do not invent defaults for `context_set_id` or dataset path — both must be explicit.
2. **Pick the DB source.** Read `tools.yaml`. Filter to `kind: source` blocks whose `type` is supported by `generate_evalbench_configs` (cloud-sql-postgres, cloud-sql-mysql, alloydb-postgres, spanner). If exactly one supported source exists, auto-select and tell the user. If multiple, list `name` + `type` and ask. If zero, stop and refer them back to `skill-autoctx-init`.
3. **Pick an output location.** Ask the user where eval artifacts should land. Default: `./eval-runs/<run_label>/` in cwd, where `<run_label>` is whatever short tag they want (source name + timestamp if they don't care). Confirm the absolute path before writing. There is **no experiment concept at this layer** — a single eval is a single run; only `skill-autoctx-hillclimb` aggregates multiple runs under an experiment.
4. **Generate configs.** Call `generate_evalbench_configs` with:
   - `output_dir` (absolute path chosen in step 3 — configs land in `<output_dir>/eval_configs/`, reports in `<output_dir>/eval_reports/`)
   - `dataset_path` (absolute)
   - `context_set_id` (full resource name)
   - `toolbox_config_path` (absolute)
   - `toolbox_source_name`
   If the tool errors, surface the message verbatim and help the user diagnose (bad source name, unsupported DB type, malformed dataset). Do not retry blindly.
5. **Run EvalBench.** Execute from the workspace root:
   ```
   uvx google-evalbench --experiment_config=<output_dir>/eval_configs/run_config.yaml
   ```
   Replace `<output_dir>` with the path passed in step 4. The runner streams output; surface the final job ID.
6. **Read the results.** The runner writes `scores.csv` and `summary.csv` into `<output_dir>/eval_reports/<job_id>/`. Read them directly with the `Read` tool — do not assume a summarization helper exists. Extract the overall score and a short breakdown of failure categories.
7. **Report back.** Give the user:
   - The overall score.
   - The job ID and the path to the report directory.
   - A short list of dominant failure categories (eg. "8 misclassified intent, 5 missing joins"). One sentence per category, not a full dump.

## Rules

- **Do not write to `state.md`, `autoctx/state.md`, or any cross-skill state file.** Evaluate is read-only on state. If the caller is `skill-autoctx-hillclimb`, it owns state internally; don't help it.
- **Do not invoke `skill-autoctx-bootstrap` or `skill-autoctx-hillclimb`.** Suggest them as next steps if the score is unsatisfying, but the user composes.
- **Do not accept a local ContextSet file as input.** Require a Context Store resource name. If the user only has a local file, point them at `upload_context_set` and stop.
- **Do not invent `generate_evalbench_configs` outputs** if the tool errors. Surface the error and stop until the user resolves it.

## Tools

- **`generate_evalbench_configs`** (MCP) — the only sanctioned way to produce EvalBench YAMLs and convert the golden dataset to internal format.
- **`uvx google-evalbench`** (shell) — runs the evaluation job. Invoked via `Bash`.
- **Read** — to parse `tools.yaml` (source selection) and read `scores.csv` / `summary.csv` after the run.
- `references/` (in this skill's folder, if present) — fallback guidance for diagnosing source-type validation errors.
