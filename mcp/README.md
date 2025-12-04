# DB Context Enrichment MCP Server

This MCP server provides a guided, interactive workflow to generate structured NL-to-SQL templates from your database schemas. It relies on the MCP Toolbox extension for database connectivity.

## Prerequisites

Before you begin, you need to have the Gemini CLI, `uv`, and the Google Cloud CLI installed and configured.

### 1. Gemini CLI
- **Installation:** The Gemini CLI binary should be pre-installed on Google Cloud Shell and Cloud Workstations. For other environments, follow the [official installation instructions](https://cloud.google.com/vertex-ai/docs/generative-ai/gemini/gemini-cli).
- **Verification:** Run `gemini --version` to ensure it's installed correctly.
- **Trusted Folder:** The first time you run `gemini` in a new directory, it will prompt you to trust the folder. Choose "Yes" to enable extensions.

### 2. uv (Python Package Installer)
`uv` is a fast Python package installer used to run this MCP server.
- **Installation (Linux & macOS):**
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Verification:** Run `uv --version`. If the command is not found, you may need to source your shell's configuration file (e.g., `source ~/.bashrc`) or restart your terminal.
- For other installation methods, see the [official `uv` documentation](https://docs.astral.sh/uv/getting-started/installation/).

### 3. Google Cloud Authentication
To access GCP database instances, you must configure Application Default Credentials (ADC).
- **Installation:** If you don't have `gcloud` installed, follow the [Google Cloud CLI installation guide](https://cloud.google.com/sdk/docs/install).
- **Login:** Run the following command and follow the prompts to authenticate:
  ```sh
  gcloud auth application-default login
  ```

## Installation

The installation process involves adding two Gemini CLI extensions.

1.  **Install the MCP Toolbox:**
    This extension provides the necessary tools to connect to your databases.
    ```sh
    gemini extensions install https://github.com/gemini-cli-extensions/mcp-toolbox
    ```

2.  **Install the DB Context Enrichment Server:**
    This is the main MCP server for the template generation workflow.
    ```sh
    gemini extensions install https://github.com/GoogleCloudPlatform/db-context-enrichment
    ```

> **Tip:** To update all extensions to their latest versions, run:
> `gemini extensions update --all`

## Configuration

### 1. Gemini API Key
The server uses the Gemini API for generation. Export your API key as an environment variable.
```sh
export GEMINI_API_KEY="YOUR_API_KEY"
```
You can get your key from [Google AI Studio](https://aistudio.google.com/apikey).

### 2. Database Connections (`tools.yaml`)
The MCP Toolbox requires a `tools.yaml` file to configure your database connections.

1.  Create a new, empty folder on your local machine. This will be your workspace.
2.  Inside that folder, create a file named `tools.yaml`.
3.  Add the configuration for your database connections. For a complete guide, see the [MCP Toolbox Getting Started Guide](https://github.com/gemini-cli-extensions/mcp-toolbox/tree/main?tab=readme-ov-file#getting-started) and the [official configuration guide](https://googleapis.github.io/genai-toolbox/getting-started/configure/).

#### Example `tools.yaml`
Here is a simple example for connecting to a Cloud SQL for PostgreSQL database. Ensure the instance has a Public IP enabled for simpler configuration.

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

1.  **Start Gemini CLI:**
    Open your terminal, navigate (`cd`) into the folder containing your `tools.yaml` file, and run `gemini`. For debugging, use the `--debug` flag:
    ```sh
    gemini --debug
    ```

2.  **Verify Integration:**
    Run `/mcp list`. You should see both `mcp-toolbox` and `DB Context Enrichment MCP` in the list with a green status.

    > **Troubleshooting:** If you see errors related to database connections, ensure:
    > - Your `tools.yaml` configuration is valid.
    > - You have configured Application Default Credentials (ADC) correctly.
    > - Your machine's IP is authorized to connect to the database instance.

3.  **Run the Workflows:**
    - To generate a broad set of templates from your database schema:
      ```sh
      /generate_bulk_templates
      ```
    - To generate a specific template for a question you have in mind:
      ```sh
      /generate_targeted_templates
      ```
    The agent will guide you through the rest of the process.

## Development with VSCode (Optional)

Using VSCode with the Gemini CLI Companion extension provides an enhanced editing and diffing experience.

1.  **Install VSCode:** Follow the [official installation instructions](https://code.visualstudio.com/download).
2.  **Install the Gemini CLI Companion Extension:** Search for "Gemini CLI Companion" in the VSCode Marketplace and install it.
3.  **Usage:**
    - Open your workspace folder (containing `tools.yaml`) in VSCode.
    - Open the integrated terminal (`Ctrl + \` or `Cmd + \``) and run `gemini`.
    - Verify the IDE extension is active by running `/ide status`.