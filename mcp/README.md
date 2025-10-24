# DB Context Enrichment MCP Server

This MCP server provides a guided, interactive workflow to generate structured NL-to-SQL templates from your database schemas. It relies on the MCP Toolbox extension for database connectivity.

## Prerequisites

Before you begin, you need to install `uv`, a fast Python package installer.

**macOS (Homebrew):**

```sh
brew install uv
```

**Linux and macOS (Shell):**

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify the installation by checking the version:

```sh
uv --version
```

For other installation methods, please refer to the [official `uv` documentation](https://docs.astral.sh/uv/getting-started/installation/).

## Installation

The installation process involves adding two Gemini CLI extensions.

### 1. Install the MCP Toolbox

This extension provides the necessary tools to connect to your databases and fetch schemas.

```sh
gemini extensions install https://github.com/gemini-cli-extensions/mcp-toolbox
```

### 2. Install the DB Context Enrichment Server

This is the main MCP server that contains the template generation workflow.

```sh
gemini extensions install https://github.com/GoogleCloudPlatform/db-context-enrichment --ref=juexinw/gemini-cli-extension
```

## Configuration

The MCP Toolbox requires a `tools.yaml` file to configure your database connections. For a complete guide, please refer to the [MCP Toolbox Getting Started Guide](https://github.com/gemini-cli-extensions/mcp-toolbox/tree/main?tab=readme-ov-file#getting-started).

1.  Create a new, empty folder on your local machine.
2.  Inside that folder, create a file named `tools.yaml`.
3.  Add the configuration for your database connections to this file. For detailed instructions on the `tools.yaml` format, see the [official configuration guide](https://googleapis.github.io/genai-toolbox/getting-started/configure/).

### Example `tools.yaml`

Here is a simple example for connecting to a Cloud SQL for PostgreSQL database.

```yaml
sources:
  my-postgres-db:
    kind: cloud-sql-postgres
    project: <your-gcp-project-id>
    region: <your-gcp-region>
    instance: <your-instance-name>
    database: <your-database-name>
    user: <your-database-user>
    password: <your-database-password>
tools:
  list_pg_schemas_tool:
    kind: postgres-list-tables
    source: my-postgres-db
    description: Use this tool to list all tables and their schemas in the PostgreSQL database.
```

## Usage

1. **Start Gemini CLI:**
    Open your terminal, navigate (`cd`) into the folder containing your `tools.yaml` file, and run the `gemini` command:

    ```sh
    gemini
    ```

2. **Verify Integration:**
    Once the Gemini CLI has started, verify that both MCP servers are correctly integrated by listing them:

    ```sh
    /mcp list
    ```

    You should see both `mcp-toolbox` and `DB Context Enrichment MCP` in the list of available servers.

3. **Start the Workflow:**
    To begin the guided template generation process, run the following command:

    ```sh
    /generate_bulk_templates
    ```

    The agent will then guide you through the rest of the process, from selecting a database to approving the final templates.
