# Project Overview

This project is a FastMCP server for "DB Context Enrichment." It provides a guided workflow to generate structured, natural language-to-SQL templates from a user's database schema.

**Crucially, this server depends on a running MCP Toolbox server to provide the underlying tools for database connection and schema fetching.**

## Key Workflow (`generate_bulk_templates` prompt)

The primary workflow guides an agent through the following steps:

1. **Discover & Select Database**: Finds connected databases (via the MCP Toolbox) and asks the user to choose one.
2. **Generate Pairs**: Calls the `generate_sql_pairs` tool to create a list of candidate Question/SQL pairs based on the database schema.
3. **Iterative Review**: The user reviews the pairs and provides feedback for refinement. This loop continues until the user approves the list.
4. **Finalize & Save**: Once approved, the `generate_templates` tool is called to create the final, detailed JSON output. The agent is then instructed to save this JSON to a local file.

## `tools.yaml` and Database Connection Formatting

The `generate_bulk_templates` workflow requires presenting a list of databases to the user in the following format:
`Connection: <connection_name> | Instance: <instance_name> | DB: <database_name>`

This information is derived from the `tools.yaml` file used by the MCP Toolbox server. Here's how the fields map from an example `tools.yaml`:

```yaml
sources:
  # This is the <connection_name>
  eval-pg-alloydb-db:
    ...
    # This is the <instance_name>
    instance: sqlgen-magic-primary
    # This is the <database_name>
    database: financial
    ...
```

-   **Connection**: The top-level key under `sources` (e.g., `eval-pg-alloydb-db`).
-   **Instance**: The value of the `instance` key.
-   **DB**: The value of the `database` key.

## Toolbox Tool Usage for Schema Fetching

When using Toolbox tools to fetch a database schema, adhere to the following:

-   **Fetching All Tables**: If the user requests "all tables," **do not** pass the `table_name` parameter. This will ensure all tables are fetched.
-   **Schema Detail**: To get the detailed schema, **do not** specify the `output_format` parameter. This will ensure the detailed schema is used by default.