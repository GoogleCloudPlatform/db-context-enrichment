import textwrap
from value_search.match_templates import MatchFunction

_SUPPORTED_DB_TYPE = ['alloydb', 'postgres', 'mysql', 'spanner']

GENERATE_TARGETED_VALUE_SEARCH_PROMPT = textwrap.dedent(
        """
        **Workflow for Generating Targeted Value Search**

        1.  **Database Configuration:**
            - Ask the user for the **Database Type (Product name) and optionally version**. Supported database types: {supported_db_types}
            - **Understand the difference between Database Type and Database Engine:**
              - **Database Type** is the product name (e.g., `alloydb`, `postgres`, `mysql`, `spanner`). This is what the user provides.
              - **Database Engine** is the underlying SQL dialect/protocol used by tools (e.g., `postgresql` for `alloydb`/`postgres`, `googlesql` for `spanner`). You MUST infer this engine from the type.
            - Using the database type provided, infer the database engine:
              - **alloydb** or **postgres** -> `postgresql`
              - **mysql** -> `mysql`
              - **spanner** -> `googlesql`
            - Confirm db type provided is one of the supported types. If not, notify the user this database type is not supported yet and end the workflow.
        
        2.  **Fetch Capabilities:**
            - **Immediately after** receiving the Database Type (and Version if provided), call the `list_match_functions` tool.
            - **Important:** Pass the **inferred database engine** (as defined in step 1) to the `db_engine` parameter of the tool.
            - If the tool returns an error (e.g., unsupported version), present the error to the user (which includes the list of supported versions) and end the workflow.
            - Otherwise, present the available match functions to the user, strictly including the function name, its Description, and an Example of when it should be used, using the information returned by the tool.

        3.  **User Input Loop:**
            - Ask the user to provide the following details for a value search:
              - **Table Name**
              - **Column Name**
              - **Concept Type** (e.g., "City", "Product ID")
              - **Match Function** (Must be one of the function names retrieved in Step 2)
              - **Engine Specific Parameters** (Ask for these if the chosen function and engine require them):
                - For **Spanner (googlesql)** + `{trigram_match}`: Ask for **Column Tokens** column name.
                - For **MySQL** + `{semantic_match}`: Ask for **Column Embedding** column name.
              - **Description** (optional): A description of the value search.
            - After capturing the details, check if the input is valid, especially whether Match Function is a valid string from the returned values from list_match_functions, if not ask the user to do a correction, if valid, ask the user if they would like to add another one.
            - Continue this loop until the user indicates they have no more value searches to add.

        4.  **Review and Confirmation:**
            - Present the complete list of user-provided value search definitions for confirmation.
              - **Use the following format for each value search:**
                **Index [Number]**
                **Table:** [Table Name]
                **Column:** [Column Name]
                **Concept:** [Concept Type]
                **Function:** [Match Function]
                **Engine Specific Parameters:** [Column Tokens / Column Embedding, if provided]
                **Description:** [Description]
            - Ask if any modifications are needed. If so, work with the user to refine the list.

        5.  **Final Generation:**
            - Once approved, call the `generate_value_searches` tool with the list of value search definitions.
            - Mapping for `generate_value_searches` input (JSON):
              - `column_tokens` (for Column Tokens)
              - `column_embedding` (for Column Embedding)
            - **Important:** Pass the **inferred db_engine** (from step 1) and `db_version` to the tool.
            - Combine all generated Value Search configurations into a single JSON structure (ContextSet).

        6.  **Save Value Search:**
            - Ask the user to choose one of the following options:
              1. Create a new context set file.
              2. Append value search to an existing context set file.

            - **If creating a new file:**
              - You will need to ask the user for the database instance and database name to create the filename.
              - Call the `save_context_set` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

            - **If appending to an existing file:**
              - Ask the user to provide the path to the existing context set file.
              - Call the `attach_context_set` tool with the JSON content and the absolute file path.

        7.  **Generate Upload URL (Optional):**
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
    ).format(
        supported_db_types=_SUPPORTED_DB_TYPE,
        trigram_match=MatchFunction.TRIGRAM_STRING_MATCH.value,
        semantic_match=MatchFunction.SEMANTIC_SIMILARITY_MATCH.value,
    )