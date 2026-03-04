---
name: database-connectivity
description: Helper for creating or updating `tools.yaml` configuration files for the GenAI Toolbox setting up database connections (AlloyDB, Cloud SQL, Spanner).
---

# Toolbox Config Helper

This skill assists users in creating and managing a valid `tools.yaml` file for the GenAI Toolbox. It supports creating a new file from scratch, adding new database connections to an existing file, and listing currently configured connections.

## Primary Workflows

### 1. Create a New `tools.yaml`
This workflow should be used when no `tools.yaml` file exists in the extension directory.

1.  **Identify Database Type**: Ask the user which database they want to configure. The supported types are:
    - Cloud SQL Postgres
    - Cloud SQL MySQL
    - AlloyDB Postgres
    - Spanner
2.  **Collect Information**: Based on the user's selection, request all **Required Information** as detailed in references/.
3.  **Generate Configuration**: Select the matching template from the reference, replace all placeholders with the user's provided values, and generate the complete `tools.yaml` content.
4.  **Save Configuration**: Offer to save the generated content to the project root directory (current directory).
5.  **Validate**: After saving, validate the new connection by using the toolbox script: `<skill_dir>/scripts/toolbox --tools-file <tools_yaml_path> invoke <data_source_name>-list-schemas`.
6.  **Apply**: Upon success validation, return the message back to the user to apply the changes by /mcp refresh

### 2. Add a Database to an Existing `tools.yaml`
This workflow should be used when a `tools.yaml` file already exists and the user wants to add a new database connection.

1.  **Identify Database Type**: Ask the user for the type of the new database connection they wish to add.
2.  **Collect Information**: Request the required information for the new connection, including a new, unique `<data_source_name>`.
3.  **Read Existing File**: Read the content of the existing `tools.yaml`.
4.  **Generate and Append**: Generate the YAML snippets for the new `sources` and `tools` sections. Append these new entries to the respective sections in the existing file content.
5.  **Save Configuration**: Save the updated content back to the `tools.yaml` file in the project root directory.
6.  **Validate**: Validate only the newly added connection using its data source name: `<skill_dir>/scripts/toolbox --tools-file <tools_yaml_path> invoke <data_source_name>-list-schemas`.
7.  **Apply**: Upon success validation, return the message back to the user to apply the changes by /mcp refresh

### 3. List Existing Database Connections
This workflow is used to check which databases are already configured.

1.  **Check and Read `tools.yaml`**: Look for and read the `tools.yaml` file in the project root directory. If it doesn't exist, inform the user.
2.  **Parse and List**: Parse the YAML content and list the names of all configured data sources. These are the top-level keys under the `sources:` section.

## Validation

To verify that a specific database connection is configured correctly at any time, run the validation script with the target data source name:
`<skill_dir>/scripts/toolbox --tools-file <tools_yaml_path> invoke <data_source_name>-list-schemas`

## Templates & Reference

For the specific fields required for each database type and the exact YAML structure to use, refer to references/.
