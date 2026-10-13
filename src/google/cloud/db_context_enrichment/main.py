import json

from fastmcp import FastMCP

from google.cloud.db_context_enrichment.common import (
    context_mutator,
    context_validator,
)
from google.cloud.db_context_enrichment.dataset import (
    dataset_generator,
    dataset_splitter,
)
from google.cloud.db_context_enrichment.evaluate import (
    evaluate_generator,
    generalizability,
    result_reader,
)

mcp = FastMCP("Context Engineering Agent MCP")


@mcp.tool
async def generate_dataset(
    dataset_entries_json: str,
    output_file_path: str,
) -> str:
    """
    Validates a list of evaluation dataset entries and saves them to a JSON file. This is the REQUIRED tool for generating 'golden' datasets.

    CRITICAL: Any request to generate an evaluation dataset MUST follow the "context-engineering-workflow" skill.
    Do NOT use generic file-writing tools to save the golden dataset. Using this tool is the final step of the dataset generation workflow.

    The workflow REQUIRES the following steps BEFORE calling this tool:
    1. Activate the `context-engineering-workflow` skill.
    2. Read the `context-engineering-dataset-generation` skill's `SKILL.md` for the full procedure.
    3. Generate mandatory audit reports (evalset_environment_inputs.md, evalset_gen_plan.md, evalset_report_pair_level.md, evalset_report_dataset_level.md) as specified in the workflow. These files are required for the verification process to pass.

    Args:
        dataset_entries_json: A JSON string representing a list of dataset items.
                             Each item should have "id", "database", "nlq", and "golden_sql" keys.
                             Example: '[{"id": "eval_001", "database": "my_db", "nlq": "Count users", "golden_sql": "SELECT COUNT(*) FROM users"}]'
        output_file_path: The absolute path where the dataset JSON file should be saved.

    Returns:
        The absolute file path where the dataset was saved.
    """
    return await dataset_generator.generate_dataset(
        dataset_entries_json, output_file_path
    )


@mcp.tool
async def split_dataset(
    golden_dataset_path: str,
    output_dir: str,
    hillclimb_ratio: float = 0.7,
    min_holdout_size: int = 45,
) -> str:
    """Splits a golden dataset into Hillclimbing and Holdout splits.

    Strictly enforces that every normalized SQL query template (key) in Holdout (holdout.json)
    is also included in Hillclimbing (hillclimb.json) with different natural language phrasings and parameters.
    Enforces a minimum holdout set size (default: 45, default ratio: 0.7, e.g., 105 Hillclimbing / 45 Holdout for 150 items).
    Saves internal partitions to <output_dir>/splits/hillclimb.json and <output_dir>/splits/holdout.json.

    Args:
        golden_dataset_path: The absolute path to the golden dataset JSON file.
        output_dir: Output directory where splits/hillclimb.json and splits/holdout.json are saved.
        hillclimb_ratio: Ratio of data for hillclimbing (default: 0.7).
        min_holdout_size: Minimum required items for holdout split (default: 45).

    Returns:
        A concise summary message confirming the split creation.
    """
    return await dataset_splitter.split_dataset(
        golden_dataset_path, output_dir, hillclimb_ratio, min_holdout_size
    )


@mcp.tool
def evaluate_generalizability(
    dev_passed: int,
    dev_total: int,
    test_passed: int,
    test_total: int,
    alpha: float = 0.05,
    diagnosis: str | None = None,
    recommended_action: str | None = None,
    next_step: str | None = None,
    context_set_id: str | None = None,
    context_file: str | None = None,
) -> str:
    """Evaluates generalizability across hillclimbing and holdout splits.

    Calculates a two-proportion pooled z-test, derives the verdict (PASS, INVESTIGATE,
    INCONCLUSIVE), and returns the formatted On-Screen Summary Card for novice users.

    Args:
        dev_passed: Number of passed queries in Hillclimbing Questions.
        dev_total: Total queries in Hillclimbing Questions (N_dev).
        test_passed: Number of passed queries in Holdout Questions.
        test_total: Total queries in Holdout Questions (N_test).
        alpha: Significance level (default: 0.05).
        diagnosis: Optional specific diagnosis text.
        recommended_action: Optional recommended action text.
        next_step: Optional immediate next step text.
        context_set_id: Optional full ContextSet resource name of the final hill-climbing iteration.
        context_file: Optional filename of the final mutated ContextSet JSON file.

    Returns:
        The markdown string for the On-Screen Summary Card.
    """
    stats = generalizability.calculate_z_test(
        dev_passed, dev_total, test_passed, test_total, alpha
    )
    return generalizability.format_on_screen_card(
        stats,
        diagnosis,
        recommended_action,
        next_step,
        context_set_id,
        context_file,
    )


@mcp.tool
def generate_evalbench_configs(
    output_dir: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_config_path: str,
    toolbox_source_name: str,
) -> str:
    """
    Generates Evalbench YAML configurations and converts the user-facing golden dataset to be compatible for evaluation, saving all files directly to disk.

    This tool writes the following files inside `<output_dir>/eval_configs/`:
    - `db_config.yaml`
    - `model_config.yaml`
    - `run_config.yaml`
    - `llmrater_config.yaml`
    - `golden_queries.json` (converted to EvalBench internal format)

    The generated `run_config.yaml` also points evalbench at
    `<output_dir>/eval_reports/` for its results.

    Args:
        output_dir: Directory (absolute or workspace-relative) where the eval configs and reports should live. Created if missing.
        dataset_path: The absolute path to the golden dataset file in the simplified user-facing format (JSON list of objects with keys: "id", "database", "nlq", "golden_sql").
        context_set_id: Full ContextSet resource name to evaluate against.
        toolbox_config_path: The absolute path to the tools.yaml configuration file.
        toolbox_source_name: The name of the database source to use inside tools.yaml. The underlying source block must use a supported 'type' (cloud-sql-postgres, cloud-sql-mysql, spanner, alloydb-postgres, bigquery, or custom).

    Returns:
        A message indicating that the configuration files were successfully created.
    """
    evaluate_generator.generate_evalbench_configs(
        output_dir,
        dataset_path,
        context_set_id,
        toolbox_config_path,
        toolbox_source_name,
    )
    return f"Successfully generated all configs for evaluation in {output_dir}/eval_configs/"


@mcp.tool
def mutate_context_set(
    file_path: str,
    mutations_json: str,
) -> str:
    """
    Apply structural mutations to an existing ContextSet JSON file.

    Parameters:
    - file_path (str): The absolute path to the ContextSet file.
    - mutations_json (str): A JSON string representing a list of mutations.
      Each mutation must contain:
      - 'operation': "add", "delete", or "update"
      - 'type': "template", "facet", or "value_search"
      - 'identifier' (dict): Required for "delete" and "update" to find the target item (e.g., {"nl_query": "What are all users?"}).
      - 'value' (dict): Required for "add" and "update".
        - For "add": Must be the FULL item body. Follow the formatting guidance in the `context-engineering-generation-guide` skill to produce well-formed content.
        - For "update": Can be a PARTIAL body containing only the fields to change (it will be merged with the existing item).

    Example 'mutations_json':
    '[
      {
        "operation": "add",
        "type": "template",
        "value": {
          "nl_query": "How many users registered in 2023?",
          "sql": "SELECT count(*) FROM users WHERE year = 2023",
          "intent": "Count users registered in 2023",
          "manifest": "Count users registered in a given year",
          "parameterized": {
            "parameterized_sql": "SELECT count(*) FROM users WHERE year = $1",
            "parameterized_intent": "Count users registered in $1"
          }
        }
      },
      {
        "operation": "delete",
        "type": "facet",
        "identifier": {"intent": "high price"}
      },
      {
        "operation": "update",
        "type": "facet",
        "identifier": {"intent": "high price"},
        "value": {"sql_snippet": "price > 2000", "intent": "very high price"}
      }
    ]'
    """
    try:
        mutations_data = json.loads(mutations_json)
        if not isinstance(mutations_data, list):
            return "Error applying mutations: mutations_json must be a JSON list."
        mutations = [context_mutator.Mutation(**mut) for mut in mutations_data]
        context_mutator.mutate_context_set(file_path, mutations)
        return f"Successfully applied {len(mutations)} mutations to {file_path}"
    except Exception as e:
        return f"Error applying mutations: {str(e)}"


@mcp.tool
def validate_context_set(file_path: str) -> str:
    """
    Validate a ContextSet JSON file for structural and convention issues. Reports issues only — does not fix them. The caller (agent) is expected to apply fixes via `mutate_context_set`, then re-run validation until `valid` is true.

    Args:
        file_path: Absolute path to the ContextSet file.

    Returns:
        A JSON string of the shape:
          {
            "valid": bool,
            "issues": [
              {
                "location": {"type": "template" | "facet" | "value_search", "index": int} | null,
                "message": str
              },
              ...
            ]
          }
    """
    return json.dumps(context_validator.validate_context_set(file_path), indent=2)


@mcp.tool
async def read_evaluation_result(
    run_folder_path: str, offset: int = 0, batch_size: int = 10
) -> str:
    """Reads evaluation results from a folder and produces a markdown summary.

    Args:
        run_folder_path: The absolute path to the evaluation run result folder, which ends with the eval run job id.
        offset: Offset to start reading failure cases from (default: 0).
        batch_size: Number of failure cases to show in the report (default: 10).

    Returns:
        A string in markdown format containing the summary and failure cases.
    """
    return result_reader.read_eval_results(run_folder_path, offset, batch_size)


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
