---
name: skill-setup-db-connection
description: Sets up and manages a tools.yaml file for the GenAI Toolbox — creating a new file, adding additional database connections, or listing existing ones. Standalone; does not assume any autoctx/ workspace layout.
---

# Database Connection Setup

This skill manages the `tools.yaml` file that the GenAI Toolbox uses to expose database connections (schema listing, SQL execution).

The default output location is `autoctx/tools.yaml` because the plugin's bundled toolbox MCP server is hard-coded to load from that path — using the default means the toolbox tools work without further configuration. The skill is otherwise standalone: it does not create the rest of the `autoctx/` workspace (`state.md`, `experiments/`), and the user can override `output_path` to write anywhere.

## Input

- `output_path` (optional): absolute or relative path where `tools.yaml` should be written. Defaults to `autoctx/tools.yaml`. If using the default and the `autoctx/` directory does not exist, create it.
- Database connection details — collected interactively (see "Credentials" below).

## Credentials

For Google Cloud databases, the system uses **Application Default Credentials (ADC)** and IAM authentication. Providing a user and password is not supported.

When collecting information from the user, inform them that only ADC is supported and they do not need to provide a username or password.

**Sample Message:**
> "I'll help you configure the database connection in `tools.yaml`. Note that the system only supports Application Default Credentials (ADC) for authentication, so you don't need to provide a username or password. Please ensure that the IAM account you are using has the required permissions to access the database.
>
> Could you please provide the following details:
> - Google Cloud Project ID:
> - Region:
> ... (other required fields based on database type)"

## Workflows

Pick the workflow that matches the user's request:

### 1. Create a New `tools.yaml`

1.  **Confirm output location:** state where the file will be written. Default is `autoctx/tools.yaml` (creates the `autoctx/` directory if missing); ask the user only if they want to override the default.
2.  **Identify database type:** ask the user which database they want to configure:
    - Cloud SQL Postgres
    - Cloud SQL MySQL
    - AlloyDB Postgres
    - Spanner
3.  **Collect information:** request all **Required Information** based on the templates inside the `references/` folder. Do NOT assume missing fields; ask the user for them explicitly.
4.  **Generate configuration:** replace all placeholders with the user's values and write the complete `tools.yaml` to `output_path`.
5.  **Validate:** confirm the new connection works:
    `npx -y @toolbox-sdk/server --config <output_path> invoke <data_source_name>-list-schemas`

### 2. Add a Database to an Existing `tools.yaml`

1.  **Identify file:** ask the user for the path to the existing `tools.yaml` (or use a provided `tools_config_path` input).
2.  **Identify database type:** ask the user for the type of the new connection.
3.  **Collect information:** request the required information, including a new unique `<data_source_name>`.
4.  **Read existing file:** load the existing `tools.yaml` content.
5.  **Generate and append:** generate the YAML snippets for the new `sources` and `tools` sections. Append to the respective sections in the existing file content.
6.  **Save configuration:** write the updated content back.
7.  **Validate:** validate only the newly added connection:
    `npx -y @toolbox-sdk/server --config <config_path> invoke <data_source_name>-list-schemas`

### 3. List Existing Database Connections

1.  **Check and read `tools.yaml`:** verify the file exists at the user-supplied path. If not, inform the user.
2.  **Parse and list:** parse the YAML and list all data source names found under the `sources:` key.

## Output

A valid `tools.yaml` file at the requested location (default `autoctx/tools.yaml`).

## Final Summary

Conclude with a succinct summary:
- State whether a new file was created, an existing file was updated, or sources were listed.
- Instruct the user to reload the MCP toolbox so the new connections take effect:
    - **Gemini CLI**: run `/mcp reload`.
    - **Claude Code**: run `/reload-plugins`.

## Templates & Reference

For the specific fields required for each database type and the exact YAML structure, refer to the `references/` directory.
