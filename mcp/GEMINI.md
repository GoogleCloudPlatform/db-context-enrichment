# Project Overview

This project is a FastMCP server for "DB Context Enrichment." It provides a guided workflow to generate structured, natural language-to-SQL templates and SQL facets from a user's database schema.

**Crucially, this server depends on a running MCP Toolbox server to provide the underlying tools for database connection and schema fetching.**

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

## SQL Validation Behavior

During the SQL validation step, the Gemini CLI will execute SQL queries using the appropriate `execute-sql` tool. It will **only report success or failure** to the user. The full query results will **not** be displayed to the user but will be used internally by the Gemini CLI for self-correction in case of query failures.

## ContextSet Management Tools

When using the `attach_context_set` tool, the Gemini CLI should **not** read the content of the existing file directly before calling the tool. The `attach_context_set` tool is designed to handle all necessary file I/O operations (reading, merging, and writing) internally, making direct file reading by the CLI redundant and potentially inefficient for large files. Similarly, when using `save_context_set`, the CLI should pass the `ContextSet` JSON directly to the tool without prior file operations.

## ContextSet Structure

The `ContextSet` object is a JSON structure that can contain both `templates` and `facets`. It is the standardized output format for `generate_templates` and `generate_facets` tools, and the expected input for `save_context_set` and `attach_context_set`.

**Example ContextSet JSON:**

```json
{
  "templates": [
    {
      "nl_query": "How many accounts are there in total?",
      "sql": "SELECT count(*) FROM account",
      "intent": "How many accounts are there in total?",
      "manifest": "How many accounts are there in total?",
      "parameterized": {
        "parameterized_sql": "SELECT count(*) FROM account",
        "parameterized_intent": "How many accounts are there in total?"
      }
    }
  ],
  "facets": [
    {
      "facet": "description LIKE '%luxury%' OR description LIKE '%premium%'",
      "intent": "luxury product",
      "manifest": "luxury product",
      "parameterized": {
        "parameterized_facet": "description LIKE '%luxury%' OR description LIKE '%premium%'",
        "parameterized_intent": "luxury product"
      }
    }
  ]
}
```