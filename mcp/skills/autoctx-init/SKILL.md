---
name: skill-autoctx-init
description: Orchestrates the initialization workflow for auto context generation, and provides helper workflow for setting up dataset connection by creating or updating tools.yaml configurations.
---

# Auto Context Generation Initialization

This skill guides the user through scaffolding a new environment for the DB Data Agent auto context generation. It handles creating tracking files, output directories, and configuring database connections.

## Initialization Workflow

Follow these steps when the user asks to initialize the environment:

1.  **Confirm Working Directory:** Explicitly state the current working directory to the user. Explain that the initialization (creating `tools.yaml`, `state.md`, `experiments/`) will occur in this directory. Ask them to confirm if this is the correct location before proceeding.
2.  **Check Existing Infrastructure:** Check if `tools.yaml`, `state.md`, AND the `experiments/` directory already exist.
    - If **all** of them exist: Inform the user that the environment is already fully initialized. Skip directly to the **Final Summary**.
    - If **any** are missing: Only proceed to create the missing items in the subsequent steps.
3.  **Setup Toolbox Configuration:** If `tools.yaml` is missing, follow the primary "1. Create a New tools.yaml" workflow documented below in the **Toolbox Config Helper** section.
4.  **Create State Tracker:** If `state.md` is missing, create it. Include a brief header “context authoring experiment state tracking”.
5.  **Initialize Experiments Directory:** If `experiments/` is missing, create an empty `experiments/` directory.

## Output

Upon successful completion, the workspace must contain:
- `tools.yaml`: A structurally sound configuration file for the Toolbox MCP Server.
- `state.md`: The external state tracker for hill-climbing iterations.
- `experiments/`: The base directory prepared to store all hill-climbing run artifacts (e.g. baseline contexts, evaluation reports).

## Final Summary

Conclude by providing a succinct summary to the user:
- State whether the workspace was initialized newly or if existing files were preserved.
- Instruct the user to run `/mcp reload` to apply any new database changes to the toolbox.
- Inform them they are now ready to proceed to the next phase (e.g., the Bootstrap workflow).

---

# Toolbox Config Helper

This section contains standalone instructions for managing the `tools.yaml` file for the GenAI Toolbox. You can execute these if the user explicitly asks to add or list database connections.

## Credentials

For Google Cloud databases, the system uses Application Default Credentials (ADC) and IAM Authentication. Providing a user and password is not supported.

When collecting information from the user, inform the user that only Application Default Credentials (ADC) are supported for authentication. They do not need to provide a username or password.

**Sample Message:**
> "I'll help you configure the database connection in `tools.yaml`. Note that the system only supports Application Default Credentials (ADC) for authentication, so you don't need to provide a username or password. Please ensure that the IAM account you are using has the required permissions to access the database.
> 
> Could you please provide the following details:
> - Google Cloud Project ID:
> - Region:
> ... (other required fields based on database type)"

## Primary Workflows

### 1. Create a New `tools.yaml`

1.  **Identify Database Type:** Ask the user which database they want to configure:
    - Cloud SQL Postgres
    - Cloud SQL MySQL
    - AlloyDB Postgres
    - Spanner
2.  **Collect Information:** Request all **Required Information** based on the templates inside the `references/` folder. Do NOT assume missing fields; ask the user for them explicitly.
3.  **Generate Configuration:** Replace all placeholders with the user's provided values and generate the complete `tools.yaml` content. Save it to the current root directory.
4.  **Validate:** After saving, validate the new connection using the toolbox script:
    `<skill_dir>/scripts/toolbox --config tools.yaml invoke <data_source_name>-list-schemas`

### 2. Add a Database to an Existing `tools.yaml`

1.  **Identify Database Type:** Ask the user for the type of the new database connection they wish to add.
2.  **Collect Information:** Request the required information for the new connection, including a new, unique `<data_source_name>`.
3.  **Read Existing File:** Read the content of the existing `tools.yaml`.
4.  **Generate and Append:** Generate the YAML snippets for the new `sources` and `tools` sections. Append these new entries to the respective sections in the existing file content.
5.  **Save Configuration:** Save the updated content back to the `tools.yaml` file.
6.  **Validate:** Validate only the newly added connection:
    `<skill_dir>/scripts/toolbox --config tools.yaml invoke <data_source_name>-list-schemas`

### 3. List Existing Database Connections

1.  **Check and Read `tools.yaml`:** Check for the `tools.yaml` file. If it doesn't exist, inform the user.
2.  **Parse and List:** Parse the YAML content and list the names of all configured data sources found under the `sources:` key limit.

## Validation

To verify that a specific database connection is configured correctly at any time, run the validation script with the target data source name:
`<skill_dir>/scripts/toolbox --config tools.yaml invoke <data_source_name>-list-schemas`

## Templates & Reference

For the specific fields required for each database type and the exact YAML structure to use, refer to the `references/` directory.
