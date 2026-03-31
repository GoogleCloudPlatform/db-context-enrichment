---
name: skill-autoctx-evaluate
description: Guides the agent to execute an evaluation of a generated ContextSet against a golden dataset utilizing the Evalbench framework.
---

# Auto Context Generation - Evaluation Workflow

This skill guides the process of rigorously evaluating an existing ContextSet against a specific golden truth dataset using Google's Evalbench architecture. It structures the evaluation experiments and executes the binaries.

## Input

Before beginning the workflow, you explicitly require:
- A `tools.yaml` file securely located in the workspace root directory containing the target database connection details.
- A golden evaluation dataset (`golden_dataset_path`), formatted as an absolute system path (e.g., `/absolute/path/to/golden_dataset.json`).
- The `context_set_id` (the Data Agent's authored context configuration identifier, retrievable by the user directly from the GCP Database Studio console; e.g., `projects/<project_id>/locations/<region>/contextSets/<context_set_name>`).

## Workflow

Follow these steps exactly in order:

1. **Experiment Selection & Memory:**
   - Scan the local `experiments/` directory and list the available tuning workflows/subfolders to the user.
   - Wait for the user to explicitly select an experiment folder to evaluate.
   - Once selected, explicitly record their chosen experiment name into the local `state.md` file to act as long-term memory so you don't forget it during subsequent evaluations.

2. **Parameter Collection:**
   - **User Inputs:** Prompt the user ONLY for the `golden_dataset_path` and the `context_set_id` (if they haven't provided them already). Do NOT ask them to explain or verify database configurations.
   - **Interactive DB Selection:** Read the `tools.yaml` file from the workspace root to list available databases to the user:
     1. Find all `kind: source` blocks with supported evaluation engines (consult the `generate_evalbench_configs` tool description for the exact list of supported types).
     2. If there is exactly one *supported* source, inform the user and auto-select it.
     3. If there are multiple *supported* sources, list their `name` and `type` and let the user select which database to evaluate.

3. **Config Generation (Core Execution):**
   - Use the `generate_evalbench_configs` MCP tool. This is the **only** way to generate Evalbench configs. Never invent configs from scratch.
   - If the tool fails, analyze the error and retry with corrected inputs. If it is an internal system error, STOP and inform the user.
   - Provide the selected `experiment_name`, `dataset_path`, `context_set_id`, absolute `toolbox_config_path` (e.g. workspace `tools.yaml`), and selected `toolbox_source_name`.
   - The tool will output the raw YAML configs mapped by filename (e.g., `run_config.yaml`, `model_config.yaml`, `db_config.yaml`).
   - Create an `eval_configs/` directory inside their chosen `experiments/<experiment_name>/` folder.
   - Write these configuration string contents into their respective physical `.yaml` files inside that new `eval_configs/` directory.

4. **Evalbench Run Integration:**
   - Trigger the `run_shell_command` natively to execute the evaluation from the ROOT of the workspace using the following exact command template:
     `<skill_dir>/scripts/evalbench --experiment_config experiments/<experiment_name>/eval_configs/run_config.yaml`
   - Check the command outputs to ensure the evaluation reports materialize in the respective `experiments/<experiment_name>/eval_reports/` directory.

## Output

Upon successful completion, the workspace must contain:
- The generated Evalbench config files successfully written to the `eval_configs/` folder.
- Evaluating reports built successfully by the external Evalbench runner process.

## Final Summary & Next Steps

Conclude by providing a succinct summary to the user:
- Confirm that the context set has been scored and point out exactly where the final metrics CSV/results are located.
- Share top-level performance summaries.
- Suggest actionable next steps (e.g., transition to a refinement workflow to hill-climb and improve the metrics based on failed evaluations).

## Templates & Reference

When listing sources from `tools.yaml`, ensure you only present `kind: source` records to the user.
The tool `generate_evalbench_configs` will find the selected block inside the file and validate its connection parameters deterministically using Python code. You do not need to manually parse or map individual properties such as `host`, `port`, or `database` yourself. If the tool indicates a verification failure for a specific database type, refer to the schema examples inside `references/` (e.g., `cloud-sql-postgres.md`) to guide the user on fixing their `tools.yaml` definition.
