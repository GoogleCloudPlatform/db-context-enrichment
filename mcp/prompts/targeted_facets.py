import textwrap

GENERATE_TARGETED_FACETS_PROMPT = textwrap.dedent(
    """
    **Workflow for Generating Targeted Facets**

    1.  **User Input Loop:**
        - Ask the user to provide an intent and its corresponding SQL snippet.
        - **Important:** Do not infer the intent or SQL snippet. Wait for the user to provide them.
        - After capturing the intent and SQL snippet pair, ask the user if they would like to add another one.
        - Continue this loop until the user indicates they have no more pairs to add.

    2.  **Review and Confirmation:**
        - Present the complete list of user-provided Intent/SQL snippet pairs for confirmation.
          - **Use the following format for each facet:**
            **Facet [Number]**
            **Intent:** [The intent]
            **SQL snippet:**
            ```sql
            [The SQL snippet, properly formatted]
            ```
        - Ask if any modifications are needed. If so, work with the user to refine the pairs.

    3.  **Final Facet Generation:**
        - Once approved, call the `generate_facets` tool with the approved pairs.
        - **Note:** If the number of approved pairs is very large (e.g., over 50), break the list into smaller chunks and call the `generate_facets` tool for each chunk.
        - The tool will return the final JSON content as a string.

    4.  **Save Facets:**
        - Ask the user to choose one of the following options:
          1. Create a new context set file.
          2. Append facets to an existing context set file.

        - **If creating a new file:**
          - You will need to ask the user for the database instance and database name to create the filename.
          - Call the `save_context_set` tool. You will need to provide the database instance, database name, the JSON content from the previous step, and the root directory where the Gemini CLI is running.

        - **If appending to an existing file:**
          - Ask the user to provide the path to the existing context set file.
          - Call the `attach_context_set` tool with the JSON content and the absolute file path.

    5.  **Generate Upload URL (Optional):**
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
)
