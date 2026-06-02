---
name: skill-bootstrap
description: Bootstraps an initial ContextSet (templates, facets, and value searches) by analyzing a target database schema and any user-provided design docs or application code. Writes the result to a user-specified file path.
---

# Bootstrap Workflow

This skill generates a baseline ContextSet from the target database's schema. It is standalone — it does **not** read or write `autoctx/`, `state.md`, or any experiment folder. All paths are inputs, supplied either by the user (when invoked directly) or by an orchestrating caller (e.g., `skill-hillclimb`).

## Input

- `tools_config_path`: absolute path to a `tools.yaml` containing the target database connection and schema-fetching tools (e.g., `<source>-list-schemas`).
- `toolbox_source_name`: the `name` of the `kind: source` block within `tools.yaml` to bootstrap against. If omitted and only one source exists, auto-select it.
- `output_file_path`: absolute path for the generated ContextSet JSON file.
- (Optional) Design docs or application code (e.g., ORM models, SQL queries) the user wishes to provide for context enrichment.

If invoked directly with no inputs pre-supplied, ask the user for each missing required input.

## Workflow

Follow these steps exactly in order:

1. **Schema Retrieval & Source Enrichment:**
   - Use the Toolbox MCP tools configured in `tools_config_path` to fetch schemas for `toolbox_source_name`.
   - Present the retrieved schema summary **structurally and cleanly** to the user. Ask if they want to filter or focus on specific schemas or tables.
   - **Source enrichment:** prompt the user for any existing design docs or application code they wish to provide. Wait for their response before proceeding.

2. **Deduce Key Info (Core Execution):**
   - Perform a **deep analysis** of the retrieved schema and any provided documentation or code to identify important concepts, relationships, and likely query patterns.
   - **Collect candidates**: identify representative natural language queries with their corresponding SQL, common filter conditions or business rules, and **columns that require specialized value searching** (e.g., names needing fuzzy match, descriptions needing semantic search).
   - *Review check:* briefly display these candidates to the user for approval or modifications before proceeding.

3. **Context Generation (Core Execution):**
   - **Invoke the `context-generation-guide` skill** to produce the context (Templates, Facets, and Value Searches).
   - Provide the deduced candidates collected in Step 2 as input to that skill.
   - That skill handles phrase extraction, parameterization, and constructing the final valid JSON structure according to dialect best practices for all context types.
   - Once generated, use the `mutate_context_set` MCP tool to save the context items to `output_file_path`. Since this is a new file, construct a list of `"operation": "add"` mutations for each generated item (Template, Facet, Value Search) and pass them to the tool.

## Output

Upon successful completion:
- A ContextSet JSON file is written to `output_file_path`.

## Upload Instructions

Conclude by providing a succinct summary to the user:

1. **Summarize results:** confirm the file has been generated and mention `output_file_path`.
2. **Upload helper:** read DB details (project, location, instance/cluster) from `tools_config_path` for `toolbox_source_name`, then call the `generate_upload_url` tool to produce a direct console link. Present the local file path and the console link together in a single message.
