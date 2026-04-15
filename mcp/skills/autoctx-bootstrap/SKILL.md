---
name: skill-autoctx-bootstrap
description: Guides the agent to bootstrap an initial context set (templates & facets) by deducing key information from the database schema and generating a ContextSet file.
---

# Auto Context Generation - Bootstrap Workflow

This skill guides the process of bootstrapping an initial ContextSet (baseline context) from the target database schema.

## Input

Before beginning the workflow, you explicitly require:
- An active `tools.yaml` configuration with database schema fetching tools configured (e.g., `<source>-list-schemas`).
- Target database schemas to act upon.

## Workflow

Follow these steps exactly in order:

1. **Condition Check & Schema Retrieval:**
   - You must explicitly ask the user for a descriptive name for this tuning experiment (e.g., `sales_db_tuning`). A new dedicated subfolder will be created inside the `experiments/` directory using this name to hold the entire tuning lifecycle and prevent any surprises. Do not proceed until you have their confirmation.
   - Use the available Toolbox MCP tools configured in the active `tools.yaml` to fetch the schemas for the target database.
   - Present the retrieved schema summary **structurally and cleanly** to the user. Ask the user if they want to filter or focus on specific schemas or tables.
   - **Source Enrichment**: Prompt the user for any existing **Design Docs** or **Application Code** (e.g., ORM models, SQL queries) they wish to provide to enrich the context generation. Wait for the user's response before proceeding.

2. **Deduce Key Info (Core Execution):**
   - Perform a **deep analysis** of the retrieved **schema and any provided documentation or code** to identify important concepts, relationships, or likely query patterns.
   - **Templates**: Deduce key information for a set of query templates. For each, you need the natural language question (`question`), the corresponding `sql`, and the overall `intent`.
   - **Facets**: Deduce key information for a set of SQL facets (reusable filters, conditions, expressions). For each, you need the `sql_snippet` and the `intent`. 
     - **Important**: Ensure `sql_snippet` uses table-qualified column names (e.g., `table.column`) to avoid ambiguity.
   - *Review Check:* Briefly display the deduced key info (templates and facets) to the user for approval or modifications before proceeding.

3. **Context Generation (Core Execution):**
   - Once the user approves the key information, use the `generate_bootstrap_context` tool.
   - You must provide the exact `output_file_path`. Save the context file inside the approved experiment folder as `bootstrap_context.json` (e.g., `experiments/sales_db_tuning/bootstrap_context.json`).
   - Pass the deduced key info as JSON parameters (`template_inputs_json`, `facet_inputs_json`) matching the tool's expected schema.
   - You must explicitly provide the `sql_dialect` parameter (e.g. `postgresql`, `mysql`, `googlesql`) as it is a required input.

## Output

Upon successful completion, the workspace must contain:
- A generated `.json` file (`bootstrap_context.json`) representing the baseline `ContextSet`, stored successfully at the requested `output_file_path`.

## Upload Advice & Next Steps

Conclude by providing a succinct summary to the user:
1. **Summarize Results**:
   - Confirm that the bootstrap context file has been successfully generated and saved.
   - Mention the final file path.
2. **Upload Instructions**:
   - Call `generate_upload_url` to get the direct link to the database studio (read project/instance details from `tools.yaml`).
   - Present the local file path to `bootstrap_context.json` and the generated console link together in a single clear message.
3. **Instruct Next Step Evaluation**:
   - Instruct the user to upload the file to Database Studio and then run evaluation using the evaluating workflow on this new ContextSet to establish a baseline.
