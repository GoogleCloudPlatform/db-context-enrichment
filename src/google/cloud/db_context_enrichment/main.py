import datetime
import json
import os

from fastmcp import FastMCP

from google.cloud.db_context_enrichment.common import context_mutator
from google.cloud.db_context_enrichment.dataset import dataset_generator
from google.cloud.db_context_enrichment.evaluate import (
    evaluate_generator,
    result_reader,
)
from google.cloud.db_context_enrichment.model import context

mcp = FastMCP("Context Engineering Agent MCP")


@mcp.tool
async def generate_dataset(
    dataset_entries_json: str,
    output_file_path: str,
) -> str:
    """
    Validates a list of evaluation dataset entries and saves them to a JSON file.

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
def generate_evalbench_configs(
    experiment_name: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_config_path: str,
    toolbox_source_name: str,
) -> str:
    """
    Generates Evalbench YAML configurations and converts the user-facing golden dataset to be compatible for evaluation, saving all files directly to disk.

    This tool writes the following files inside `experiments/<experiment_name>/eval_configs/`:
    - `db_config.yaml`
    - `model_config.yaml`
    - `run_config.yaml`
    - `llmrater_config.yaml`
    - `golden_queries.json` (converted to EvalBench internal format)

    Args:
        experiment_name: The name of the target experiment folder.
        dataset_path: The absolute path to the golden dataset file in the simplified user-facing format (JSON list of objects with keys: "id", "database", "nlq", "golden_sql").
        context_set_id: The specific context_set_id inside the experiment.
        toolbox_config_path: The absolute path to the tools.yaml configuration file.
        toolbox_source_name: The name of the database source to use inside tools.yaml. The underlying source block must use a supported 'type' (cloud-sql-postgres, cloud-sql-mysql, spanner, alloydb-postgres).

    Returns:
        A message indicating that the configuration files were successfully created.
    """
    evaluate_generator.generate_evalbench_configs(
        experiment_name,
        dataset_path,
        context_set_id,
        toolbox_config_path,
        toolbox_source_name,
    )
    return f"Successfully generated all configs for evaluation in experiments/{experiment_name}/eval_configs/"


@mcp.tool
def generate_upload_url(
    db_engine: str,
    project_id: str,
    location: str | None = None,
    cluster_id: str | None = None,
    instance_id: str | None = None,
    database_id: str | None = None,
) -> str:
    """
    Generates a URL for uploading the template file based on the database engine.

    Args:
        db_engine: The database engine. Accepted values are 'alloydb',
                 'cloudsql', or 'spanner'. This can be derived from the 'kind'
                 field in the tools.yaml file. For example, 'alloydb-postgres'
                 becomes 'alloydb', and 'cloud-sql-postgres' becomes 'cloudsql'.
        project_id: The Google Cloud project ID.
        location: The location of the AlloyDB cluster.
        cluster_id: The ID of the AlloyDB cluster.
        instance_id: The ID of the Cloud SQL or Spanner instance.
        database_id: The ID of the Spanner database.

    Returns:
        The generated URL as a string, or an error message if the source kind is invalid.
    """
    if db_engine == "alloydb":
        if location and cluster_id and project_id:
            return f"https://console.cloud.google.com/alloydb/locations/{location}/clusters/{cluster_id}/studio?project={project_id}"
        else:
            return "Error: Missing location, cluster_id, or project_id for alloydb."
    elif db_engine == "cloudsql":
        if instance_id and project_id:
            return f"https://console.cloud.google.com/sql/instances/{instance_id}/studio?project={project_id}"
        else:
            return "Error: Missing instance_id or project_id for cloudsql."
    elif db_engine == "spanner":
        if instance_id and database_id and project_id:
            return f"https://console.cloud.google.com/spanner/instances/{instance_id}/databases/{database_id}/details/query?project={project_id}"
        else:
            return "Error: Missing instance_id, database_id, or project_id for spanner."
    else:
        return "Error: Invalid db_engine. Must be one of 'alloydb', 'cloudsql', or 'spanner'."





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
        - For "add": Must be the FULL item body. Rely on specialized generation tools (like `generate_templates`) to produce this content deterministically.
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
