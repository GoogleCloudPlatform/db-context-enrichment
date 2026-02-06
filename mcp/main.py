from fastmcp import FastMCP
from typing import List
import textwrap
from template import question_generator, template_generator
from facet import facet_generator
from value_search import generator as vi_generator
from value_search import match_templates
from model import context
import prompts
import datetime
import os
import json

mcp = FastMCP("DB Context Enrichment MCP")


@mcp.tool
async def generate_sql_pairs(
    db_schema: str,
    context: str | None = None,
    table_names: List[str] | None = None,
    sql_dialect: str | None = None,
) -> str:
    """
    Generates a list of question/SQL pairs based on a database schema.

    Args:
        db_schema: A string containing the database schema.
        context: Optional user feedback or context to guide generation.
        table_names: Optional list of table names to focus on. If the user
          mentions all tables, ignore this field. The default behavior is to use
          all tables for the pair generation.
        sql_dialect: Optional name of the database engine for SQL dialect.

    Returns:
        A JSON string representing a list of dictionaries, where each dictionary
        has a "question" and a "sql" key.
        Example: '[{"question": "...", "sql": "..."}]'
    """
    return await question_generator.generate_sql_pairs(
        db_schema, context, table_names, sql_dialect
    )


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
async def generate_value_searches(
    value_search_inputs_json: str,
    db_engine: str,
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
            
        db_engine: The database engine (postgresql, mysql, etc.).
        db_version: The database version (optional).
        
    Returns:
        A JSON string representing a ContextSet object containing all the new value searches.
    """
    if db_version and not db_version.strip():
        db_version = None
    
    return vi_generator.generate_value_searches(
        value_search_inputs_json, db_engine, db_version
    )

@mcp.tool
def list_match_functions(db_engine: str, db_version: str | None = None) -> str:
    """
    Lists the valid match template function names for a specific database engine.
    Use this to show the user what 'match_function' options are available.
    
    If the engine or version is not supported, this will return an error message
    listing the valid options.

    Args:
        db_engine: The database engine (e.g., 'postgresql').
        db_version: The specific database version (optional).
    
    Returns:
        A JSON string containing the list of available function names, 
        or an error message if validation fails.
    """
    try:
        functions = match_templates.get_available_functions(db_engine, db_version)
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
    db_type: str,
    project_id: str,
    location: str | None = None,
    cluster_id: str | None = None,
    instance_id: str | None = None,
    database_id: str | None = None,
) -> str:
    """
    Generates a URL for uploading the template file based on the database type.

    Args:
        db_type: The type of the database. Accepted values are 'alloydb',
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
    if db_type == "alloydb":
        if location and cluster_id and project_id:
            return f"https://console.cloud.google.com/alloydb/locations/{location}/clusters/{cluster_id}/studio?project={project_id}"
        else:
            return "Error: Missing location, cluster_id, or project_id for alloydb."
    elif db_type == "cloudsql":
        if instance_id and project_id:
            return f"https://console.cloud.google.com/sql/instances/{instance_id}/studio?project={project_id}"
        else:
            return "Error: Missing instance_id or project_id for cloudsql."
    elif db_type == "spanner":
        if instance_id and database_id and project_id:
            return f"https://console.cloud.google.com/spanner/instances/{instance_id}/databases/{database_id}/details/query?project={project_id}"
        else:
            return "Error: Missing instance_id, database_id, or project_id for spanner."
    else:
        return "Error: Invalid db_type. Must be one of 'alloydb', 'cloudsql', or 'spanner'."


@mcp.prompt
def generate_bulk_templates() -> str:
    """Initiates a guided workflow to automatically generate templates based on the database schema."""
    return prompts.GENERATE_BULK_TEMPLATES_PROMPT


@mcp.prompt
def generate_targeted_templates() -> str:
    """Initiates a guided workflow to generate specific templates based on the user's input."""
    return prompts.GENERATE_TARGETED_TEMPLATES_PROMPT


@mcp.prompt
def generate_targeted_facets() -> str:
    """Initiates a guided workflow to generate specific facets based on the user's input."""
    return prompts.GENERATE_TARGETED_FACETS_PROMPT

@mcp.prompt
def generate_targeted_value_search() -> str:
    """Initiates a guided workflow to generate specific Value Search configurations."""
    return prompts.GENERATE_TARGETED_VALUE_SEARCH_PROMPT


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
