from fastmcp import FastMCP
from typing import List
import textwrap
from template import template_generator
from facet import facet_generator
from value_search import generator as vi_generator
from value_search import match_templates
from model import context
import prompts
import datetime
import os
import json
from bootstrap import bootstrap_generator
from evaluate import evaluate_generator
from evaluate import result_reader
from dataset import dataset_generator
from common import context_mutator


mcp = FastMCP("DB Context Enrichment MCP")


@mcp.tool
async def generate_templates(
    template_inputs_json: str, sql_dialect: str = "postgresql"
) -> str:
    """
    Generates final templates from a list of user-approved template question, template SQL statement, and optional template intent.

    Args:
        template_inputs_json: A JSON string representing a list of dictionaries (template inputs),
                             where each dictionary has "question", "sql", and optional "intent" keys.
                             Example (with intent): '[{"question": "How many users?", "sql": "SELECT count(*) FROM users", "intent": "Count total users"}]'
                             Example (default intent): '[{"question": "List all items", "sql": "SELECT * FROM items"}]'
        sql_dialect: The SQL dialect to use for parameterization. Accepted
                   values are 'postgresql' (default), 'mysql', or 'googlesql'.

    Returns:
        A JSON string representing a ContextSet object.
    """
    return await template_generator.generate_templates(
        template_inputs_json, sql_dialect
    )


@mcp.tool
async def generate_facets(
    facet_inputs_json: str, sql_dialect: str = "postgresql"
) -> str:
    """
    Generates final facets from a list of user-approved facet intent and facet SQL snippet.

    Args:
        facet_inputs_json: A JSON string representing a list of dictionaries (facet inputs),
                             where each dictionary has "intent" and "sql_snippet".
                             Example: '[{"intent": "high price", "sql_snippet": "price > 1000"}]'
        sql_dialect: The SQL dialect to use for parameterization. Accepted
                   values are 'postgresql' (default), 'mysql', or 'googlesql'.

    Returns:
        A JSON string representing a ContextSet object.
    """
    return await facet_generator.generate_facets(
        facet_inputs_json, sql_dialect
    )


@mcp.tool
async def generate_bootstrap_context(
    output_file_path: str,
    template_inputs_json: str | None = None,
    facet_inputs_json: str | None = None,
    sql_dialect: str = "postgresql"
) -> str:
    """
    Generates a single unified ContextSet from key information and saves it to a file.

    Args:
        output_file_path: The absolute path where the JSON ContextSet file should be saved.
        template_inputs_json: A JSON string representing a list of extracted seed information used to generate full templates.
            Each item in the list should be a dictionary with keys:
            - "question": The natural language question.
            - "sql": The corresponding SQL query to answer the question.
            - "intent": (Optional) A brief description of the intent.
            
            Example: 
            '[{"question": "How many users?", "sql": "SELECT COUNT(*) FROM users", "intent": "Count total users"}]'
            
        facet_inputs_json: A JSON string representing a list of extracted seed information used to generate full facets.
            Each item in the list should be a dictionary with keys:
            - "intent": A brief description of the facet intent.
            - "sql_snippet": A specific SQL fragment (such as a filter condition) representing the intent.
            
            Example: 
            '[{"intent": "high price", "sql_snippet": "price > 1000"}]'
        sql_dialect: SQL engine dialect.
        
    Returns:
        The absolute file path pointing to the generated and saved ContextSet JSON.
    """
    return await bootstrap_generator.generate_context(
        output_file_path, sql_dialect, template_inputs_json, facet_inputs_json
    )


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
    return await dataset_generator.generate_dataset(dataset_entries_json, output_file_path)


@mcp.tool
def generate_evalbench_configs(
    experiment_name: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_config_path: str,
    toolbox_source_name: str
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
        experiment_name, dataset_path, context_set_id, toolbox_config_path, toolbox_source_name
    )
    return f"Successfully generated all configs for evaluation in experiments/{experiment_name}/eval_configs/"


@mcp.tool
async def generate_value_searches(
    value_search_inputs_json: str,
    dialect: str,
    db_version: str | None = None,
) -> str:
    """
    Generates final value searches from a list of user-approved value search definitions.

    Args:
        value_search_inputs_json: A JSON string representing a list of value search definitions.
            Each item in the list should be a dictionary with keys:
            - "table_name": The name of the table.
            - "column_name": The name of the column.
            - "concept_type": The semantic type (e.g., 'City').
            - "match_function": The match function to use (e.g., 'EXACT_MATCH_STRINGS').
            - "description": (Optional) A description of the value search.
            
            Example:
            '[
                {"table_name": "users", "column_name": "city", "concept_type": "City", "match_function": "EXACT_MATCH_STRINGS"},
                {"table_name": "products", "column_name": "name", "concept_type": "Product", "match_function": "FUZZY_MATCH_STRINGS"}
            ]'
            
        dialect: The database dialect (postgresql, mysql, etc.).
        db_version: The database version (optional).
        
    Returns:
        A JSON string representing a ContextSet object containing all the new value searches.
    """
    if db_version and not db_version.strip():
        db_version = None
    
    return vi_generator.generate_value_searches(
        value_search_inputs_json, dialect, db_version
    )


@mcp.tool
def list_match_functions(dialect: str, db_version: str | None = None) -> str:
    """
    Lists the valid match template functions with their descriptions and examples for a specific database dialect.
    Use this to show the user what 'match_function' options are available, along with their details.
    
    If the dialect or version is not supported, this will return an error message
    listing the valid options.

    Args:
        dialect: The database dialect (e.g., 'postgresql').
        db_version: The specific database version (optional).
    
    Returns:
        A JSON string containing a dictionary of available function names mapped to their descriptions and examples,
        or an error message if validation fails.
    """
    try:
        functions = match_templates.get_available_functions(dialect, db_version)
        return json.dumps(functions)
    except ValueError as e:
        return f"Error: {str(e)}"


@mcp.tool
def save_context_set(
    context_set_json: str,
    db_instance: str,
    db_name: str,
    output_dir: str,
) -> str:
    """
    Saves a ContextSet to a new JSON file with a generated timestamp.

    Args:
        context_set_json: The JSON string of the ContextSet.
        db_instance: The database instance name.
        db_name: The database name.
        output_dir: The directory to save the file in. The root of where the
          Gemini CLI is running.

    Returns:
        A confirmation message with the path to the newly created file.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{db_instance}_{db_name}_context_set_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    try:
        data = json.loads(context_set_json)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return f"Successfully saved context set to {filepath}"
    except (json.JSONDecodeError, IOError) as e:
        return f"Error saving file: {e}"


@mcp.tool
def attach_context_set(
    context_set_json: str,
    file_path: str,
) -> str:
    """
    Attaches a ContextSet to an existing JSON file.

    This tool reads an existing JSON file containing a ContextSet,
    appends new templates/facets/value_searches to it, and writes the updated ContextSet
    back to the file. Exceptions are propagated to the caller.

    Args:
        context_set_json: The JSON string output from the generation tools.
        file_path: The **absolute path** to the existing template file.

    Returns:
        A confirmation message with the path to the updated file.
    """

    existing_content_dict = {"templates": [], "facets": [], "value_searches": []}
    if os.path.getsize(file_path) > 0:
        with open(file_path, "r") as f:
            existing_content_dict = json.load(f)

    existing_context = context.ContextSet(**existing_content_dict)

    new_context = context.ContextSet(**json.loads(context_set_json))

    if existing_context.templates is None:
        existing_context.templates = []
    if new_context.templates:
        existing_context.templates.extend(new_context.templates)

    if existing_context.facets is None:
        existing_context.facets = []
    if new_context.facets:
        existing_context.facets.extend(new_context.facets)

    if existing_context.value_searches is None:
        existing_context.value_searches = []
    if new_context.value_searches:
        existing_context.value_searches.extend(new_context.value_searches)

    with open(file_path, "w") as f:
        json.dump(existing_context.model_dump(), f, indent=2)

    return f"Successfully attached context to {file_path}"


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


@mcp.prompt
def generate_targeted_templates() -> str:
    """Initiates a guided workflow to generate specific templates based on the user's input."""
    return prompts.GENERATE_TARGETED_TEMPLATES_PROMPT


@mcp.prompt
def generate_targeted_facets() -> str:
    """Initiates a guided workflow to generate specific facets based on the user's input."""
    return prompts.GENERATE_TARGETED_FACETS_PROMPT

@mcp.prompt
def generate_targeted_value_searches() -> str:
    """Initiates a guided workflow to generate specific Value Search configurations."""
    return prompts.GENERATE_TARGETED_VALUE_SEARCH_PROMPT


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
async def read_evaluation_result(run_folder_path: str, offset: int = 0, batch_size: int = 10) -> str:
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
