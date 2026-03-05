import textwrap

CONTEXT_BOOTSTRAP_PROMPT = textwrap.dedent(
    """
    **Workflow for Bootstrapping Database Context**

    This workflow uses a dedicated tool to analyze a database schema and generate a high-quality, natural language-to-SQL context. This process depends on a running **MCP Toolbox server** for database connection and schema fetching.

    1.  **Select Database:**
        - Ask the user to select a database using the available Toolbox tools.
        - You may need to list connections first if the user hasn't specified one.
        - Format the database choice as: `Connection: <connection_name> | Instance: <instance_name> | DB: <database_name>` (derived from the Toolbox `tools.yaml`).

    2.  **Fetch Schema:**
        - Once a database is selected, fetch its detailed schema using the appropriate Toolbox tool.
        - **Fetch All Tables**: Do not pass the `table_name` parameter to fetch all tables.
        - **Schema Detail**: Do not specify the `output_format` parameter to ensure a detailed schema is used.

    3.  **Clean up Schema:**
        - Review the fetched schema.
        - **Remove Noise**: Using your own reasoning, strip out system tables, internal metadata, and any tables that are clearly not business-relevant.
        - **Focus**: Keep only the core tables that a user would likely query (e.g., users, orders, products).
        - Use this cleaned-up schema for the next step.

    4.  **One-Shot Context Bootstrapping and Storage:**
        - Once the schema is fetched, call the `bootstrap_context` tool.
        - Pass the `db_schema` (the cleaned version) and the **absolute path** to the directory where you are currently running (`output_dir`).
        - The tool will:
            - Propose Template and Facet inputs using an LLM.
            - Automatically parameterize them using the internal generation logic.
            - Save the `ContextSet` JSON in the specified `output_dir` with a `bootstrap` prefix and timestamp.
            - Return a summary containing the final file path and the generated content.

    5.  **Review and Completion:**
        - Present the resulting file path and the `ContextSet` content to the user.

    Start by helping the user **Select a Database** from the Toolbox.
    """
)
