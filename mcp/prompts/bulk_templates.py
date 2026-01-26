import textwrap

GENERATE_BULK_TEMPLATES_PROMPT = textwrap.dedent(
    """
    **Workflow for Automatically Generating Templates**

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
        - **Important:** The user can optionally customize the "intent" for any pair. If they do, make sure to include it in the final JSON passed to the tool.

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
