# Project Overview

This project is a FastMCP server for "DB Context Enrichment." It provides a guided workflow to generate structured, natural language-to-SQL templates from a user's database schema.

**Crucially, this server depends on a running MCP Toolbox server to provide the underlying tools for database connection and schema fetching.**

## Key Workflow (`generate_bulk_templates` prompt)

The primary workflow guides an agent through the following steps:

1. **Discover & Select Database**: Finds connected databases (via the MCP Toolbox) and asks the user to choose one.
2. **Generate Pairs**: Calls the `generate_sql_pairs` tool to create a list of candidate Question/SQL pairs based on the database schema.
3. **Iterative Review**: The user reviews the pairs and provides feedback for refinement. This loop continues until the user approves the list.
4. **Finalize & Save**: Once approved, the `generate_templates` tool is called to create the final, detailed JSON output. The agent is then instructed to save this JSON to a local file.

## Tool Descriptions

- `generate_sql_pairs(db_schema, context, table_names, db_engine, num_pairs)`: Takes a database schema and optional parameters to generate a list of candidate Question/SQL pairs for user review.
- `generate_templates(approved_pairs_json)`: Takes a user-approved JSON string of Question/SQL pairs and transforms them into the final, detailed, and parameterized template format.
