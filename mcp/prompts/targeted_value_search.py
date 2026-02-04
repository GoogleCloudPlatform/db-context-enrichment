import textwrap

GENERATE_TARGETED_VALUE_SEARCH_PROMPT = textwrap.dedent(
        """
        **Workflow for Generating Targeted Value Search**

        1.  **Database Configuration:**
            - Ask the user for the **Database Engine and optionally version**.
        
        2.  **Fetch Capabilities:**
            - **Immediately after** receiving the Database Engine (and Version if provided), call the `list_match_functions` tool.
            - If the tool returns an error (e.g., unsupported version), present the error to the user (which includes the list of supported versions) and end the workflow.
            - Otherwise, use the returned list of available match functions in the next step to specify what all functions are supported.

        3.  **User Input Loop:**
            - Ask the user to provide the following details for a value search:
              - **Table Name**
              - **Column Name**
              - **Concept Type** (e.g., "City", "Product ID")
              - **Match Function** (Must be one of the functions retrieved in Step 2)
              - **Description** (optional): A description of the value search.
            - After capturing the details, ask the user if they would like to add another one.
            - Continue this loop until the user indicates they have no more value searches to add.

        4.  **Review and Confirmation:**
            - Present the complete list of user-provided value search definitions for confirmation.
              - **Use the following format for each value search:**
                **Index [Number]**
                **Table:** [Table Name]
                **Column:** [Column Name]
                **Concept:** [Concept Type]
                **Function:** [Match Function]
                **Description:** [Description]
            - Ask if any modifications are needed. If so, work with the user to refine the list.

        5.  **Final Generation:**
            - Once approved, call the `generate_value_searches` tool with the list of value search definitions.
            - **Important:** Pass the `db_engine` and `db_version` collected in Step 1 to the tool.
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
            - If the user confirms, you must collect the necessary database context from them.
            - **Supported Database Types:** Inform the user that currently only `alloydb` is supported.
            - **Collect:**
              - **Project ID:** The Google Cloud project ID.
              - **Location:** The AlloyDB location.
              - **Cluster ID:** The AlloyDB cluster ID.
            - Once you have the required information, call the `generate_upload_url` tool to provide the upload URL to the user.

        Start the workflow.
        """
    )