---
name: skill-hillclimb
description: Orchestrates the end-to-end hill-climbing loop for a ContextSet — selects/creates an experiment, runs evaluation, analyzes failures, mutates the context, uploads, and repeats. Owns the autoctx/ workspace structure and delegates the standalone tasks (bootstrap, evaluation) to dedicated skills.
---

# Hill-Climbing Workflow (Orchestrator)

This skill is the **orchestrator** for the entire automated context refinement loop. It owns the `autoctx/` workspace structure (`autoctx/state.md`, `autoctx/experiments/<name>/`, per-iteration folders) and is the single place where experiment selection, loop bookkeeping, and sub-skill invocation live.

It delegates focused tasks to standalone skills:
- **`skill-bootstrap`** — to generate a baseline ContextSet when a new experiment is created without a pre-existing context.
- **`skill-evaluate`** — to run each iteration's evaluation against the current ContextSet.

When invoking these sub-skills, this orchestrator passes all inputs explicitly so the sub-skills never re-prompt the user.

> [!IMPORTANT]
> **Constraint**: in this workflow, you are only allowed to use context types `templates` and `facets` for mutations. Do not attempt to use other context types.

## Inputs Recorded Per Experiment

The orchestrator records the following in `autoctx/state.md` for each experiment so they aren't re-asked across iterations:

- `tools_config_path` (defaults to `autoctx/tools.yaml` — the path the plugin's bundled toolbox MCP server uses; user can override on first experiment setup).
- `toolbox_source_name` (the database source within tools.yaml).
- `dataset_path` (absolute path to the golden evaluation dataset).
- `context_set_id` (current — updated each loop after upload).
- `base_context_path` (path to the v0/baseline context for this experiment).

---

## 1. Setup & Loop Identification

1.  **Scaffold the workspace if missing**:
    -   If `autoctx/` does not exist in the current working directory, create it along with `autoctx/state.md` (header: `# Context Authoring Experiment State Tracking`) and an empty `autoctx/experiments/` directory. Inform the user that the workspace was created.
    -   If `autoctx/` exists but is missing `state.md` or `experiments/`, create the missing pieces.
2.  **Identify or Create Experiment**:
    -   Read `autoctx/state.md` to identify the active experiment. If found, confirm with the user that they want to continue with it.
    -   If no active experiment, list `autoctx/experiments/` (may be empty) and ask the user to either select an existing one or create a new one.
    -   **Creating a new experiment**:
        -   Ask for a descriptive name (e.g., `sales_db_tuning`) and create `autoctx/experiments/<name>/`.
        -   **Determine `tools_config_path`**: default to `autoctx/tools.yaml`. If that file exists, confirm with the user. If it does not exist, ask the user for an alternate path or tell them to run `/autoctx:setup-db-connection` to create one, then resume. Record the chosen path in `autoctx/state.md`.
        -   Ask the user how they want to seed the baseline context:
            1. **Bootstrap a new baseline**: invoke `skill-bootstrap` with:
               - `tools_config_path=<recorded value>`
               - `toolbox_source_name=<ask user, or auto-select if only one>`
               - `output_file_path=autoctx/experiments/<name>/bootstrap_context.json`
               Then set `base_context_path` to the output path.
            2. **Use an existing context file**: ask the user for the absolute path and record it as `base_context_path`.
               - Inform the user that the context must be uploaded to GCP Database Studio to obtain a `context_set_id`.
        -   Record the chosen experiment name as the active experiment in `autoctx/state.md`.
3.  **Collect or Recall Loop Inputs**:
    -   Read `autoctx/state.md` for the experiment's `tools_config_path`, `toolbox_source_name`, `dataset_path`, and `context_set_id`.
    -   For any missing values (typically the first iteration), prompt the user. Persist what you collect back into `autoctx/state.md` so subsequent iterations don't re-ask.
4.  **Determine Loop Version**:
    -   Scan `autoctx/experiments/<name>/hillclimb/` for files matching `improved_context_v*.json`.
    -   Determine the loop version `vN` as `max(N) + 1`, or `v1` if the folder is empty.
5.  **Locate Base Context for This Iteration**:
    -   For `v1`: use the recorded `base_context_path`.
    -   For `vN` (N > 1): use `autoctx/experiments/<name>/hillclimb/improved_context_v(N-1).json`.
    -   Verify the file exists. If missing, STOP and ask the user for the correct path.

---

## 2. Evaluate the Current Context

1.  **Invoke the evaluation skill** (`skill-evaluate`) in **generate-and-run** mode, passing all inputs directly so the sub-skill does not re-prompt the user:
    -   `tools_config_path` = recorded value
    -   `toolbox_source_name` = recorded value
    -   `context_set_id` = current value from `autoctx/state.md`
    -   `dataset_path` = recorded value
    -   `output_dir` = `autoctx/experiments/<name>/eval_vN/` (per-iteration so configs and reports stay traceable across loops)
2.  **Capture the report location** returned by the eval skill and record it in `autoctx/state.md` under Loop `vN`.
3.  If the eval skill fails, STOP and report the error to the user.

---

## 3. Gap Analysis

1.  **Validation**:
    -   Verify the eval report folder produced in the previous step contains expected files (e.g., `scores.csv`, `summary.csv`). If missing or empty, STOP and inform the user.
2.  **Read Evaluation Results**: use the `read_evaluation_result` MCP tool passing the report folder path from the previous step.
3.  **Generate Gap Analysis Report (Batched)**:
    -   The tool returns a summary and a batch of failure cases (default limit 10).
    -   Iterate through the failures by calling the tool with increasing `offset` (0, 10, 20, ...) until all failed queries are analyzed.
    -   **First batch (offset=0)**: initialize the report file with `# Gap Analysis Report - vN` and `## Summary`, followed by the first batch under `## Failed Queries Detail`.
    -   **Subsequent batches**: call the tool with the next offset, analyze the new failures, and **append** them to the `## Failed Queries Detail` section.

    Use the following structure for the report:

    ```markdown
    # Gap Analysis Report - vN

    ## Summary
    - **Total Queries**: 10
    - **Passed**: 7
    - **Failed**: 3
    - **Pass Rate**: 70%

    ## Failed Queries Detail

    ### Query 1: "How many users registered in 2023?"
    - **Error Category**: `[FilterError]`
    - **Expected SQL**: `SELECT count(*) FROM users WHERE year = 2023`
    - **Actual SQL**: `SELECT count(*) FROM users` (Missing filter)
    - **Root Cause**: The LLM did not know about the `year` column or how to filter by year for this entity.
    - **Proposed Mutation**: Add a facet for "Users by Year".

    ### Query 2: "Show me top selling products"
    - **Error Category**: `[OrderingError]`
    - **Expected SQL**: `SELECT name FROM products ORDER BY sales DESC LIMIT 5`
    - **Actual SQL**: `SELECT name FROM products LIMIT 5`
    - **Root Cause**: Missing ordering instruction in context.
    - **Proposed Mutation**: Update the template for "Product Sales" to include ordering.

    ### Query 3: "Get users older than 30"
    - **Error Category**: `[GoldenDataError]`
    - **Expected SQL**: `SELECT * FROM users WHERE age >> 30` (Syntax error `>>` in golden SQL)
    - **Actual SQL**: `SELECT * FROM users WHERE age > 30`
    - **Root Cause**: Invalid syntax in golden dataset.
    - **Proposed Mutation**: None. Flag to user to fix the evaluation dataset.
    ```
4.  **Save Report**: physically write the report to `autoctx/experiments/<name>/hillclimb/gap_analysis_vN.md`. If processing in batches, append until all failures are documented. The file must exist on disk.
5.  **Log in State Tracking**:
    -   Update `autoctx/state.md` to record the mapping for Loop `vN` (Base Context ↔ Eval Report ↔ Gap Analysis).
6.  **Human-in-the-Loop Review**:
    -   Inform the user the Gap Analysis report has been written to disk.
    -   Ask if they want to review, correct, or add manual feedback to the file before proceeding to Context Mutation.
    -   Wait for user confirmation before starting Context Mutation.

---

## 4. Context Mutation

1.  **Validation**: verify `gap_analysis_vN.md` exists and contains findings. Verify the base ContextSet file exists. If missing, STOP and inform the user.
2.  **Analyze Gap Report & Determine Fixing Strategy**:
    -   Read `gap_analysis_vN.md` to identify what needs to be fixed.
    -   **Fixing strategy guidelines**:
        -   **Conciseness**: use *less context* to cover *more scenarios*. Avoid adding redundant or hyper-specific templates for every single edge case.
        -   **Generalizability**: prefer solutions that generalize (e.g., a `facet` for a column definition rather than a specific `template` for every query using that column).
        -   **Supported types**: support mutations for `template`, `facet`, and `value_search`.
3.  **Apply Mutations**:
    -   **Copy the base context** to the new destination: `autoctx/experiments/<name>/hillclimb/improved_context_vN.json`.
    -   **Generate new items**: for any "add" operations identified in the fixing strategy:
        -   Invoke the `context-generation-guide` skill to produce the final parameterized items.
        -   Provide the identified candidates to that skill.
        -   That skill handles phrase extraction, parameterization, and constructing the valid JSON structure.
    -   **Validate new items**:
        -   **Templates**: run generated SQL examples via `<source>-execute-sql` (use dummy values for placeholders) to verify syntax.
        -   **Others**: cross-check table/column references against the schema via `<source>-list-schemas`.
    -   **Apply mutations**: call the `mutate_context_set` MCP tool passing the **new** file path as `file_path` and mutations as `mutations_json`.
4.  **Log in State Tracking**:
    -   Update `autoctx/state.md` to include the output path of `improved_context_vN.json` for Loop `vN`.

---

## 5. Upload & Loop Decision

1.  **Summarize Improvements**: tell the user what was changed (e.g., added 2 facets, updated 1 template).
2.  **Upload Instructions**:
    -   Read DB details (project, location, instance/cluster) from the recorded `tools_config_path` for the active source.
    -   Call the `generate_upload_url` tool with those values to provide a direct console link.
    -   Present the local file path to `improved_context_vN.json` and the generated console link together in a single clear message.
3.  **Capture the new `context_set_id`**:
    -   After the user uploads, ask them for the new `context_set_id` and update `autoctx/state.md` so the next iteration evaluates against it.
4.  **Loop or Stop**:
    -   Ask the user whether to start loop `v(N+1)`. If yes, return to **Evaluate the Current Context** with the updated `context_set_id`. If no, finalize the run summary.

---

## Output

Upon successful completion of a loop iteration, the workspace must contain (for that `vN`):
-   `autoctx/experiments/<name>/eval_vN/` — generated Evalbench configs and the Evalbench report folder.
-   `autoctx/experiments/<name>/hillclimb/gap_analysis_vN.md`
-   `autoctx/experiments/<name>/hillclimb/improved_context_vN.json`
-   Updated `autoctx/state.md` with the loop's lineage.

---

## Logging State Example (`autoctx/state.md`)

When updating `autoctx/state.md`, append or update the experiment section:

```markdown
# Context Authoring Experiment State Tracking

## Active Experiment: my-exp-1

### Inputs
- tools_config_path: autoctx/tools.yaml
- toolbox_source_name: my-alloydb-source
- dataset_path: /path/to/golden_dataset.json
- context_set_id: projects/.../contextSets/my-exp-1-v3
- base_context_path: autoctx/experiments/my-exp-1/bootstrap_context.json

### Hill-Climbing Run Log

#### Loop: v1
- **Base Context**: `autoctx/experiments/my-exp-1/bootstrap_context.json`
- **Eval Output**: `autoctx/experiments/my-exp-1/eval_v1/` (configs + report)
- **Gap Analysis**: `autoctx/experiments/my-exp-1/hillclimb/gap_analysis_v1.md`
- **Mutated Context**: `autoctx/experiments/my-exp-1/hillclimb/improved_context_v1.json`
```
