# DB Context Enrichment MCP Server

This MCP server provides a guided, interactive workflow to generate structured NL-to-SQL templates from your database schemas. It relies on the MCP Toolbox extension for database connectivity.

## Prerequisites

Before you begin, you need to have the Gemini CLI and the Google Cloud CLI installed and configured.

### 1. Gemini CLI
- **Installation:** The Gemini CLI binary should be pre-installed on Google Cloud Shell and Cloud Workstations. For other environments, follow the [official installation instructions](https://cloud.google.com/vertex-ai/docs/generative-ai/gemini/gemini-cli).
- **Verification:** Run `gemini --version` to ensure it's installed correctly.
- **Trusted Folder:** The first time you run `gemini` in a new directory, it will prompt you to trust the folder. Choose "Yes" to enable extensions.

### 2. Google Cloud Authentication
To access GCP database instances and the Gemini API, you must configure Application Default Credentials (ADC) and set a quota project.
- **Installation:** If you don't have `gcloud` installed, follow the [Google Cloud CLI installation guide](https://cloud.google.com/sdk/docs/install).
- **Login:** Run the following commands and follow the prompts to authenticate and select your quota project:
  ```sh
  gcloud auth application-default login
  gcloud auth application-default set-quota-project <YOUR_QUOTA_PROJECT_ID>
  ```

## Installation

The installation process is straightforward via the Gemini CLI:

```sh
gemini extensions install https://github.com/GoogleCloudPlatform/db-context-enrichment
```

*(Note: The [`toolbox`](https://github.com/googleapis/genai-toolbox) dependency for database connection is bundled automatically within this extension.)*

> **Tip:** To update all extensions to their latest versions, run:
> `gemini extensions update --all`

## Configuration

### Database Connections (`tools.yaml`)
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
    Once initialized, the extension provides several pre-built workflows for you to use. You can discover all available workflows by typing `/` in the Gemini CLI interface to prompt autocomplete.
    
    Select a command such as `/generate_bulk_templates` or `/generate_targeted_templates`, and the agent will guide you through the rest of the interactive process!

## Development with VSCode (Optional)

Using VSCode with the Gemini CLI Companion extension provides an enhanced editing and diffing experience.

1.  **Install VSCode:** Follow the [official installation instructions](https://code.visualstudio.com/download).
2.  **Install the Gemini CLI Companion Extension:** Search for "Gemini CLI Companion" in the VSCode Marketplace and install it.
3.  **Usage:**
    - Open your workspace folder (containing `tools.yaml`) in VSCode.
    - Open the integrated terminal (`Ctrl + \` or `Cmd + \`) and run `gemini`.
    - Verify the IDE extension is active by running `/ide status`.

## Development Process

### 1. Release Pipeline
- Releases are versioned and prepared automatically by the Release Please GitHub App.
- When functional PRs are merged, Release Please opens/updates a pending Release PR (bumping the extension version and updating the changelog).
- **Merging the Release PR** signals Release Please to tag the commit and create an official GitHub Release.
- **The creation of the GitHub Release** triggers the `.github/workflows/release.yml` pipeline.
- The pipeline uses PyInstaller to build standalone binary executables for Linux (x64), macOS (arm64), and Windows (x64).
- The pipeline packages the binary, `LICENSE`, `GEMINI.md`, and dynamically updates `gemini-extension.json` into `.tar.gz` and `.zip` archives.
- These archives are automatically attached back to the GitHub release as downloadable assets.
- Users receive the update the next time they install or upgrade the extension via Gemini CLI (`gemini extensions update --all`).

### 2. Local Development
For local testing and contributions, you can run the extension directly from the source code. This method creates a symlink to your local source code, so any changes you make are immediately reflected in the CLI.

1. Install [`uv`](https://docs.astral.sh/uv/), the fast Python package installer.
2. Install the companion `mcp-toolbox` extension (which is normally bundled into production distributions) manually to supply database connections:
   ```sh
   gemini extensions install https://github.com/gemini-cli-extensions/mcp-toolbox
   ```
3. Link the `db-context-enrichment` extension locally (from the repository root):
   ```sh
   gemini extension link .
   ```