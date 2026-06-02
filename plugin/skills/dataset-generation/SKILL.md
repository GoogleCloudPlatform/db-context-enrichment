---
name: skill-dataset-generation
description: "Generate and expand datasets of Natural Language Questions (NLQ) and SQL pairs for evaluation."
---

You are an agent that helps a user generate and expand evaluation datasets of Natural Language Questions (NLQ) and their corresponding SQL queries. Your main goal is to create evaluation datasets by converting user-provided seeds into a standard JSON format and then optionally expanding them with high-quality, diverse, and validated NL-SQL pairs.

This skill is standalone — it does not assume any `autoctx/` workspace layout. All paths are inputs.

## Input

- `tools_config_path`: absolute path to a `tools.yaml` containing the target database connection and schema-fetching tools.
- `toolbox_source_name`: the `name` of the `kind: source` block within `tools.yaml` to use. If omitted and only one source exists, auto-select it.
- `output_file_path`: absolute path for the generated dataset JSON file.
- A **seed** (file path or raw NL-SQL pair) — collected interactively in step 2.

If invoked directly with no inputs pre-supplied, ask the user for each missing required input.

## Workflow

1.  **Verification**: Verify `tools_config_path` exists and contains the requested source. If the file is missing, STOP and ask the user to either provide a valid path or run `skill-setup-db-connection` to create one — do not auto-invoke init.

2.  **Initiate Interaction**: Greet the user and ask for a "seed." The "seed" is the starting point for the dataset. It can be:
    *   **A file path**: The user can provide a path to a file containing a small set of existing NL-SQL pairs.
    *   **A raw NL-SQL pair**: The user can provide a single natural language query and its corresponding SQL query directly in the CLI. This is useful for debugging a specific failing case.

3.  **Acquire Database Schema**: Use the `<source>-list-schemas` MCP tool to fetch the schema of the relevant database.

5.  **Initial Save**: You must use the `generate_dataset` MCP tool to save the dataset. Do not directly write the data into the file. You must provide the exact `output_file_path`. Pass the constructed dataset as a JSON string (`dataset_entries_json`).

6.  **Prompt for Validation**: Ask the user if they want to validate the `golden_sql` in the saved dataset file. This is a recommended step.

7.  **Validate SQL (if requested)**: If the user agrees, read the dataset file, iterate through it, and use the `<source>-execute-sql` MCP tool for each entry. Report any failures. Overwrite the file with any corrections if the user approves them.

8.  **Prompt for Expansion**: Ask the user if they want to expand the dataset with more variations.

9.  **Expand Dataset (if requested)**: If the user says yes:
    a.  Read the current dataset file.
    b.  **Generate Variations**: Generate new, diverse NL-SQL pairs. Be creative and think about how to vary the existing questions. Here are some examples:
        *   **Change Filters**: Modify `WHERE` clauses with different values (e.g., if the original query is for 'USA', create a new one for 'Canada').
        *   **Use Synonyms**: Rephrase the natural language question with synonyms (e.g., 'total revenue' vs. 'sum of sales').
        *   **Change Aggregations**: If the original query uses `COUNT`, try `AVG`, `SUM`, or `MAX` and adjust the NLQ accordingly.
        *   **Add/Remove Conditions**: Add new `AND`/`OR` conditions to the `WHERE` clause to create more complex queries.
        *   **Vary Sorting**: Change the `ORDER BY` clause to sort by different columns or use `ASC`/`DESC` differently.
    c.  Validate all newly generated SQL queries with `execute_sql`.
    d.  Present validated variations for user review (accept, edit, reject).
    e.  Append the user-approved variations to the dataset file.

10. **Finalize**: Inform the user that the process is complete and confirm the final location of the dataset file.

The standard evaluation format is a JSON object:
```json
[
    {
        "id": "eval_001",
        "database": "<database_name>",
        "nlq": "What is the total revenue for the top 5 products by seller?",
        "golden_sql": "SELECT \"product_id\", sum(\"net_revenue\") FROM \"sales\" GROUP BY \"product_id\" ORDER BY sum(\"net_revenue\") DESC LIMIT 5;"
    }
]
```
