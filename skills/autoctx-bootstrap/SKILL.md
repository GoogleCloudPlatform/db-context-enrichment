---
name: skill-autoctx-bootstrap
description: Guides the agent to bootstrap an initial context set (templates & facets) by deducing key information from the database schema and generating a ContextSet file.
---

# Auto Context Generation - Bootstrap Workflow

This skill guides the process of bootstrapping an initial ContextSet (baseline context) from the target database schema.

## Input

Before beginning the workflow, you explicitly require:
- An active `tools.yaml` configuration (located in `autoctx/`) with database schema fetching tools configured (e.g., `<source>-list-schemas`).
- Target database schemas to act upon.

## Workflow

Follow these steps exactly in order:

1. **Condition Check & Schema Retrieval:**
   - You must explicitly ask the user for a descriptive name for this tuning experiment (e.g., `sales_db_tuning`). A new dedicated subfolder will be created inside the `autoctx/experiments/` directory using this name to hold the entire tuning lifecycle and prevent any surprises. Do not proceed until you have their confirmation.
   - Use the available Toolbox MCP tools configured in the active `autoctx/tools.yaml` to fetch the schemas for the target database.
   - Present the retrieved schema summary **structurally and cleanly** to the user. Ask the user if they want to filter or focus on specific schemas or tables.
   - **Source Enrichment**: Prompt the user for any existing **Design Docs** or **Application Code** (e.g., ORM models, SQL queries) they wish to provide to enrich the context generation. Wait for the user's response before proceeding.

2. **Deduce Key Info (Core Execution):**
   - Perform a **deep analysis** of the retrieved **schema and any provided documentation or code** to identify important concepts, relationships, and likely query patterns.
   - **Collect Candidates**: Identify representative natural language queries with their corresponding SQL, common filter conditions or business rules, and **columns that require specialized value searching** (e.g., names needing fuzzy match, descriptions needing semantic search).
   - *Review Check:* Briefly display these candidates to the user for approval or modifications before proceeding.

3. **Context Generation (Core Execution):**
   - **Invoke the `context-generation-guide` skill** to produce the context (Templates, Facets, and Value Searches).
   - Provide the deduced candidates collected in Step 2 as input to that skill.
   - That skill will handle phrase extraction, parameterization, and constructing the final valid JSON structure according to dialect best practices for all context types.
   - Once generated, use the `mutate_context_set` tool to save the context items to `bootstrap_context.json` inside the approved experiment folder. Since this is a new file, construct a list of `"operation": "add"` mutations for each generated item (Template, Facet, Value Search) and pass them to the tool.

## Output

Upon successful completion, the workspace must contain:
- A generated `.json` file (`bootstrap_context.json`) representing the baseline `ContextSet`, stored successfully at the requested `output_file_path`.

## Upload Advice & Next Steps

Conclude by providing a succinct summary to the user:
1. **Summarize Results**:
   - Confirm that the bootstrap context file has been successfully generated and saved.
   - Mention the final file path.
2. **Upload Instructions**:
   - **Read Database Details**: Read `autoctx/tools.yaml` to fetch the specific project, location, and instance/cluster details for the active database.
   - **Generate URL**: Call the `generate_upload_url` tool passing the extracted values to provide the direct console link to the user.
   - Present the local file path to `bootstrap_context.json` and the generated console link together in a single clear message.
3. **Instruct Next Step Evaluation**:
   - Instruct the user to upload the file to Database Studio and then run evaluation using the evaluating workflow on this new ContextSet to establish a baseline.
