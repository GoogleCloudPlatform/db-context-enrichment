from fastmcp import FastMCP
from typing import Optional, List
import textwrap
from template import question_generator, template_generator
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
        A JSON string containing a list of question/SQL pairs.
    """
    return await question_generator.generate_sql_pairs_from_schema(
        db_schema, context, table_names, db_engine
    )


@mcp.tool
async def generate_templates(approved_pairs_json: str) -> str:
    """
    Generates final templates from a list of user-approved question/SQL pairs.
    """
    return await template_generator.generate_templates_from_pairs(approved_pairs_json)


@mcp.tool
def save_templates(
    templates_json: str,
    db_instance: str,
    db_name: str,
    output_dir: str,
) -> str:
    """
    Saves templates to a new JSON file with a generated timestamp.

    Args:
        templates_json: The JSON string of the templates.
        db_instance: The database instance name.
        db_name: The database name.
        output_dir: The directory to save the file in. The root of where the
          Gemini CLI is running.

    Returns:
        A confirmation message with the path to the newly created file.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{db_instance}_{db_name}_templates_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    try:
        data = json.loads(templates_json)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return f"Successfully saved templates to {filepath}"
    except (json.JSONDecodeError, IOError) as e:
        return f"Error saving file: {e}"


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

        1.  **Verify Integration & Discover Databases:**
            - Check for available schema tools on the MCP Toolbox server and look for a `tools.yaml` file.
            - Combine this information to deduce a list of available, connected databases.

        2.  **Database Selection:**
            - Present the list of discovered databases to the user in a compact, single-line format. 
              - **Use the following format for each database:**
                - Connection: my-prod-db | Instance: sql-server-123 | DB: customer_data
            - Ask the user to choose one for template generation. **Remember the database name.**

        3.  **Schema Analysis:**
            - Fetch the schema for the selected database. To get the detailed schema, do not specify the `output_format` parameter.
            - Present a summary of tables to the user.

        4.  **Scope Definition:**
            - Ask the user to specify tables for generation (or all tables).

        5.  **Initial Pair Generation:**
            - Call the `generate_sql_pairs` tool with the collected information.

        6.  **Iterative User Review & Refinement:**
            - Parse the JSON from the tool and present the Question/SQL pairs to the user. 
              - **Use the following format for each pair:**
                **Pair [Number]**
                **Question:** [The natural language question]
                **SQL:**
                ```sql
                [The SQL query, properly formatted]
                ```
            - Ask for approval to proceed or for feedback.
            - If feedback is given, handle minor edits or major regenerations by calling `generate_sql_pairs` again with the feedback as context.
            - Repeat until the user approves the list.

        7.  **Final Template Generation:**
            - Once approved, call the `generate_templates` tool with the approved pairs.
            - The tool will return the final JSON content as a string.

        8.  **Save Templates:**
            - Ask the user to choose one of the following options:
              1. Create a new template file.
              2. Append to an existing template file.

            - **If creating a new file:**
              - Call the `save_templates` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

            - **If appending to an existing file:**
              - Ask the user to provide the path to the existing template file.
              - Use client-side tools to read the existing file, merge the new templates with the existing ones, and write the combined list back to the file.

        9.  **Review and Upload:**
            - After the file is saved, ask the user for review.
            - Upon confirmation, call the `generate_upload_url` tool to provide a URL for uploading the template file.
        """
    )


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
