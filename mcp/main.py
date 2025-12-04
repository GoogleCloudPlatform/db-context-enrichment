from fastmcp import FastMCP
from typing import Optional, List
import textwrap
from template import question_generator, template_generator
from fragment import fragment_generator
from model import context
import datetime
import os
import json

mcp = FastMCP("DB Context Enrichment MCP")


@mcp.tool
async def generate_sql_pairs(
    db_schema: str,
    context: Optional[str] = None,
    table_names: Optional[List[str]] = None,
    db_engine: Optional[str] = None,
) -> str:
    """
    Generates a list of question/SQL pairs based on a database schema.

    Args:
        db_schema: A string containing the database schema.
        context: Optional user feedback or context to guide generation.
        table_names: Optional list of table names to focus on. If the user
          mentions all tables, ignore this field. The default behavior is to use
          all tables for the pair generation.
        db_engine: Optional name of the database engine for SQL dialect.

    Returns:
        A JSON string representing a list of dictionaries, where each dictionary
        has a "question" and a "sql" key.
        Example: '[{"question": "...", "sql": "..."}]'
    """
    return await question_generator.generate_sql_pairs_from_schema(
        db_schema, context, table_names, db_engine
    )


@mcp.tool
async def generate_templates(
    approved_pairs_json: str, db_engine: Optional[str] = "postgresql"
) -> str:
    """
    Generates final templates from a list of user-approved question/SQL pairs.

    Args:
        approved_pairs_json: A JSON string representing a list of dictionaries,
                             where each dictionary has a "question" and a "sql" key.
                             Example: '[{"question": "...", "sql": "..."}]'
        db_engine: The SQL dialect to use for parameterization. Accepted
                   values are 'postgresql', 'mysql', or 'googlesql'.

    Returns:
        A JSON string representing a ContextSet object.
    """
    # Ensure we pass a string, defaulting to 'postgresql' if None is provided.
    dialect = db_engine if db_engine is not None else "postgresql"
    return await template_generator.generate_templates_from_pairs(
        approved_pairs_json, dialect
    )


@mcp.tool
async def generate_fragments(
    approved_pairs_json: str, db_engine: Optional[str] = "postgresql"
) -> str:
    """
    Generates final fragments from a list of user-approved question/SQL fragment pairs.

    Args:
        approved_pairs_json: A JSON string representing a list of dictionaries,
                             where each dictionary has a "question" and a "fragment" key.
                             Example: '[{"question": "...", "fragment": "..."}]'
        db_engine: The SQL dialect to use for parameterization. Accepted
                   values are 'postgresql', 'mysql', or 'googlesql'.

    Returns:
        A JSON string representing a ContextSet object.
    """
    # Ensure we pass a string, defaulting to 'postgresql' if None is provided.
    dialect = db_engine if db_engine is not None else "postgresql"
    return await fragment_generator.generate_fragments_from_pairs(
        approved_pairs_json, dialect
    )


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
    appends new templates/fragments to it, and writes the updated ContextSet
    back to the file. Exceptions are propagated to the caller.

    Args:
        context_set_json: The JSON string output from the `generate_templates` or `generate_fragments` tool.
        file_path: The **absolute path** to the existing template file.

    Returns:
        A confirmation message with the path to the updated file.
    """

    existing_content_dict = {"templates": [], "fragments": []}
    if os.path.getsize(file_path) > 0:
        with open(file_path, "r") as f:
            existing_content_dict = json.load(f)

    existing_context = context.ContextSet(**existing_content_dict)

    new_context = context.ContextSet(**json.loads(context_set_json))

    if existing_context.templates is None:
        existing_context.templates = []
    if new_context.templates:
        existing_context.templates.extend(new_context.templates)

    if existing_context.fragments is None:
        existing_context.fragments = []
    if new_context.fragments:
        existing_context.fragments.extend(new_context.fragments)

    with open(file_path, "w") as f:
        json.dump(existing_context.model_dump(), f, indent=2)

    return f"Successfully attached templates to {file_path}"


@mcp.tool
def generate_upload_url(
    db_type: str,
    project_id: str,
    location: Optional[str] = None,
    cluster_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    database_id: Optional[str] = None,
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
    """Initiates a guided workflow to generate Question/SQL pair templates."""
    return textwrap.dedent(
        """
        **Workflow for Generating Question/SQL Pair Templates**

        1.  **Discover and Select Database:**
            - Find all connected databases from the MCP Toolbox and `tools.yaml`.
            - If only one database is found, present it and ask for confirmation. Do not proceed without user confirmation.
            - If multiple databases are found, present the list and ask the user to choose one.
            - Use the format: `Connection: <name> | Instance: <instance> | DB: <db>`
            - Remember the selected database name.

        2.  **Schema Analysis:**
            - Fetch the schema for the selected database. To get the detailed schema, do not specify the `output_format` parameter.
            - Present a summary of tables to the user.

        3.  **Scope Definition:**
            - Ask the user to specify tables for generation (or all tables).

        4.  **Initial Pair Generation:**
            - Call the `generate_sql_pairs` tool with the collected information.

        5.  **Iterative User Review & Refinement:**
            - Parse the JSON from the tool and present the Question/SQL pairs to the user.
              - **Use the following format for each pair:**
                **Pair [Number]**
                **Question:** [The natural language question]
                **SQL:**
                ```sql
                [The SQL query, properly formatted]
                ```
            - Ask for approval to proceed or for feedback.
            - If feedback is given, the Gemini CLI will assess the scope of the
              changes. If the feedback affects a few pairs, it will edit the
              *in-memory list* of SQL queries directly. If it impacts most pairs,
              it will call `generate_sql_pairs` again with the feedback as context
              to regenerate the list.
            - Repeat until the user approves the list.

        6.  **Optional SQL Verification and Self-Correction:**
            - After the user approves the list of pairs, ask if they would like to
              validate the SQL queries.
            - If the user agrees:
              - Identify the appropriate `execute-sql` tool from the MCP Toolbox
                (`tools.yaml`) by matching the `source` field with the database
                connection used for schema fetching and ensuring the `kind` is an
                `execute-sql` type (e.g., `postgres-execute-sql`).
              - If a suitable `execute-sql` tool cannot be found, inform the user
                with details and skip the validation step.
              - Otherwise, execute each SQL statement using the identified tool, and only report success or failure, without displaying the full query results.
            - If a query fails, the Gemini CLI will attempt to self-correct it using
              the error message as context (up to 2 retries).
            - **Crucially, ensure all pairs are validated before presenting the
              final results.**
            - Present the final, validated list to the user, noting any
              corrections or persistent failures.

        7.  **Final Template Generation:**
            - Once approved, call the `generate_templates` tool with the approved pairs.
            - **Note:** If the number of approved pairs is very large (e.g., over 50), break the list into smaller chunks and call the `generate_templates` tool for each chunk.
            - The tool will return the final JSON content as a string.

        8.  **Save Templates:**
            - Ask the user to choose one of the following options:
              1. Create a new context set file.
              2. Append templates to an existing context set file.

            - **If creating a new file:**
              - Call the `save_context_set` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

            - **If appending to an existing file:**
              - Ask the user to provide the path to the existing context set file.
              - Call the `attach_context_set` tool with the JSON content and the absolute file path.

        9.  **Review and Upload:**
            - After the file is saved, ask the user for review.
            - Upon confirmation, call the `generate_upload_url` tool to provide a URL for uploading the context set file.

        Start the workflow.
        """
    )


@mcp.prompt
def generate_targeted_templates() -> str:
    """Initiates a guided workflow to generate specific Question/SQL pair templates."""
    return textwrap.dedent(
        """
        **Workflow for Generating Targeted Question/SQL Pair Templates**

        1.  **User Input Loop:**
            - Ask the user to provide a natural language question and its corresponding SQL query.
            - After capturing the pair, ask the user if they would like to add another one.
            - Continue this loop until the user indicates they have no more pairs to add.

        2.  **Review and Confirmation:**
            - Present the complete list of user-provided Question/SQL pairs for confirmation.
              - **Use the following format for each pair:**
                **Pair [Number]**
                **Question:** [The natural language question]
                **SQL:**
                ```sql
                [The SQL query, properly formatted]
                ```
            - Ask if any modifications are needed. If so, work with the user to refine the pairs.

        3.  **Final Template Generation:**
            - Once approved, call the `generate_templates` tool with the approved pairs.
            - **Note:** If the number of approved pairs is very large (e.g., over 50), break the list into smaller chunks and call the `generate_templates` tool for each chunk.
            - The tool will return the final JSON content as a string.

        4.  **Save Templates:**
            - Ask the user to choose one of the following options:
              1. Create a new context set file.
              2. Append templates to an existing context set file.

            - **If creating a new file:**
              - You will need to ask the user for the database instance and database name to create the filename.
              - Call the `save_context_set` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

            - **If appending to an existing file:**
              - Ask the user to provide the path to the existing context set file.
              - Call the `attach_context_set` tool with the JSON content and the absolute file path.

        5.  **Generate Upload URL (Optional):**
            - After the file is saved, ask the user if they want to generate a URL to upload the context set file.
            - If the user confirms, you must collect the necessary database context from them. This includes:
              - **Database Type:** 'alloydb', 'cloudsql', or 'spanner'.
              - **Project ID:** The Google Cloud project ID.
              - **And depending on the database type:**
                - For 'alloydb': Location and Cluster ID.
                - For 'cloudsql': Instance ID.
                - For 'spanner': Instance ID and Database ID.
            - Once you have the required information, call the `generate_upload_url` tool to provide the upload URL to the user.

        Start the workflow.
        """
    )


@mcp.prompt
def generate_targeted_fragments() -> str:
    """Initiates a guided workflow to generate specific Phrase/SQL fragment pair templates."""
    return textwrap.dedent(
        """
        **Workflow for Generating Targeted Phrase/SQL Fragment Pair Templates**

        1.  **User Input Loop:**
            - Ask the user to provide a natural language phrase and its corresponding SQL fragment.
            - After capturing the pair, ask the user if they would like to add another one.
            - Continue this loop until the user indicates they have no more pairs to add.

        2.  **Review and Confirmation:**
            - Present the complete list of user-provided Phrase/SQL fragment pairs for confirmation.
              - **Use the following format for each pair:**
                **Pair [Number]**
                **Phrase:** [The natural language phrase]
                **Fragment:**
                ```sql
                [The SQL fragment, properly formatted]
                ```
            - Ask if any modifications are needed. If so, work with the user to refine the pairs.

        3.  **Final Fragment Generation:**
            - Once approved, call the `generate_fragments` tool with the approved pairs.
            - **Note:** If the number of approved pairs is very large (e.g., over 50), break the list into smaller chunks and call the `generate_fragments` tool for each chunk.
            - The tool will return the final JSON content as a string.

        4.  **Save Fragments:**
            - Ask the user to choose one of the following options:
              1. Create a new context set file.
              2. Append fragments to an existing context set file.

            - **If creating a new file:**
              - You will need to ask the user for the database instance and database name to create the filename.
              - Call the `save_context_set` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

            - **If appending to an existing file:**
              - Ask the user to provide the path to the existing context set file.
              - Call the `attach_context_set` tool with the JSON content and the absolute file path.

        5.  **Generate Upload URL (Optional):**
            - After the file is saved, ask the user if they want to generate a URL to upload the context set file.
            - If the user confirms, you must collect the necessary database context from them. This includes:
              - **Database Type:** 'alloydb', 'cloudsql', or 'spanner'.
              - **Project ID:** The Google Cloud project ID.
              - **And depending on the database type:**
                - For 'alloydb': Location and Cluster ID.
                - For 'cloudsql': Instance ID.
                - For 'spanner': Instance ID and Database ID.
            - Once you have the required information, call the `generate_upload_url` tool to provide the upload URL to the user.

        Start the workflow.
        """
    )


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
