from fastmcp import FastMCP
from typing import Optional, List
import textwrap
from template import generator

mcp = FastMCP("DB Context Enrichment MCP")


@mcp.tool
async def generate_sql_pairs(
    db_schema: str,
    context: Optional[str] = None,
    table_names: Optional[List[str]] = None,
    db_engine: Optional[str] = None,
    num_pairs: int = 10,
) -> str:
    """
    Generates a list of question/SQL pairs based on a database schema.

    Args:
        db_schema: A string containing the database schema.
        context: Optional user feedback or context to guide generation.
        table_names: Optional list of table names to focus on.
        db_engine: Optional name of the database engine for SQL dialect.
        num_pairs: The number of pairs to generate.

    Returns:
        A JSON string containing a list of question/SQL pairs.
    """
    return await generator.generate_sql_pairs_from_schema(
        db_schema, context, table_names, db_engine, num_pairs
    )


@mcp.prompt
def generate_templates() -> str:
    """Initiates a guided workflow to generate Question/SQL pair templates."""
    return textwrap.dedent(
        """
        **Workflow for Generating Question/SQL Pair Templates**

        1.  **Verify Integration:**
            - Confirm that the MCP Toolbox is integrated.
            - Check for available database schema tools (e.g., 'list_mssql_schemas', 'list_alloydb_schemas').

        2.  **Database Selection:**
            - List the available database connections based on the discovered schema tools.
            - Ask the user to choose which database to generate templates for.

        3.  **Schema Analysis:**
            - Call the appropriate MCP Toolbox tool to fetch the schema for the user's selected database.
            - Present a brief report to the user, listing the tables found in the schema.

        4.  **Scope Definition:**
            - Ask the user if they want to generate templates for all tables or only for a specific list of tables.
            - Ask the user how many template pairs they want to generate, noting that the default is 10.

        5.  **Template Generation:**
            - Call the `generate_sql_pairs` tool with the information gathered:
                - `db_schema`: The schema fetched in step 3.
                - `table_names`: The specific list of tables, if provided by the user.
                - `db_engine`: The database type (e.g., 'mssql', 'alloydb'), inferred from the tool used in step 3.
                - `num_pairs`: The number specified by the user, if provided by the user.

        6.  **User Review:**
            - Present the generated list of Question/SQL pairs to the user for their review and feedback.
        """
    )


if __name__ == "__main__":
    mcp.run()  # Uses STDIO transport by default
