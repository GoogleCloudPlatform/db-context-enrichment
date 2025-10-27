from fastmcp import FastMCP
from typing import Optional, List
import textwrap
from template import question_generator, template_generator

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
        table_names: Optional list of table names to focus on.
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
            - Fetch the schema for the selected database and present a summary of tables to the user.

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
            - Construct a filename using the database name from Step 2 and a current timestamp (e.g., `<db_name>_templates_YYYYMMDDHHMMSS.json`).
            - Use a client-side file writing tool to save the JSON content from Step 7 to the generated filename in the current directory.
        """
    )


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
