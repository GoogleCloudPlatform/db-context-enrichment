import json
from pathlib import Path

from fastmcp import FastMCP

from google.cloud.db_context_enrichment.common import context_mutator
from google.cloud.db_context_enrichment.common.context_store_client import (
    ContextStoreClient,
)
from google.cloud.db_context_enrichment.dataset import dataset_generator
from google.cloud.db_context_enrichment.evaluate import evaluate_generator
from google.cloud.db_context_enrichment.model.context import ContextSet

mcp = FastMCP("Context Engineering Agent MCP")

_CONTEXT_STORE_LOCATION = "us-central1"


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

    The runner emits eval reports under `<output_dir>/eval_reports/`.

    Args:
        output_dir: Absolute path of the directory where this eval run's configs and reports should live. Caller supplies — no experiment concept at this layer.
        dataset_path: The absolute path to the golden dataset file in the simplified user-facing format (JSON list of objects with keys: "id", "database", "nlq", "golden_sql").
        context_set_id: The Context Store resource name of the ContextSet to evaluate.
        toolbox_config_path: The absolute path to the tools.yaml configuration file.
        toolbox_source_name: The name of the database source to use inside tools.yaml. The underlying source block must use a supported 'type' (cloud-sql-postgres, cloud-sql-mysql, spanner, alloydb-postgres).

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
def upload_context_set(
    local_file_path: str,
    csg_id: str,
    cs_id: str,
    version: str,
) -> str:
    """
    Upload a local ContextSet JSON file to the Context Store. Idempotent on
    the ContextSetGroup — it is created if absent. Returns the full resource
    name of the uploaded ContextSet, suitable for downstream tools like
    `generate_evalbench_configs` or `download_context_set`.

    Args:
        local_file_path: Absolute path to a ContextSet JSON file.
        csg_id: ContextSetGroup ID (eg. an experiment name). Created if absent.
        cs_id: ContextSet ID (eg. "autoctx"). Stable across versions.
        version: Version label (eg. "baseline", "v1"). Each version is
                 immutable; uploading the same (cs_id, version) twice returns
                 a 409 error.

    Returns:
        On success: full resource name, eg.
        `projects/<p>/locations/<l>/contextSetGroups/<csg_id>/contextSets/<cs_id>@<version>`.
        On failure: an error string including the upstream HTTP status.
    """
    try:
        text = Path(local_file_path).read_text()
        ctx = ContextSet.model_validate_json(text)
        client = ContextStoreClient(location=_CONTEXT_STORE_LOCATION)
        csg_name = client.ensure_context_set_group(csg_id)
        resource_name = client.create_context_set(csg_name, cs_id, version)
        client.upload_context_set(resource_name, ctx)
        return resource_name
    except Exception as e:
        return f"Error uploading context set: {e}"


@mcp.tool
def download_context_set(resource_name: str, output_file_path: str) -> str:
    """
    Download a ContextSet from the Context Store and write it to a local
    JSON file.

    Args:
        resource_name: Full resource name as returned by `upload_context_set`.
        output_file_path: Absolute path where the JSON file should be written.

    Returns:
        The output file path on success, or an error string on failure.
    """
    try:
        client = ContextStoreClient(location=_CONTEXT_STORE_LOCATION)
        ctx = client.download_context_set(resource_name)
        Path(output_file_path).write_text(
            ctx.model_dump_json(exclude_none=True, indent=2)
        )
        return output_file_path
    except Exception as e:
        return f"Error downloading context set: {e}"


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
        - For "add": Must be the FULL item body. Follow the formatting guidance in the `context-generation-guide` skill to produce well-formed content.
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
      },
      {
        "operation": "add",
        "type": "value_search",
        "value": {
          "concept_type": "City",
          "query": "SELECT T.\\"city\\" AS value, 'users.city' AS columns, 'City' AS concept_type, fuzzy_distance(T.\\"city\\", $value) AS distance FROM \\"users\\" T WHERE fuzzy_match(T.\\"city\\", $value)",
          "description": "Fuzzy match for city in users.city"
        }
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


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
