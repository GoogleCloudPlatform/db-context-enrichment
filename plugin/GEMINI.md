# Context Engineering Agent

This project is a Gemini CLI extension for "Context Engineering Agent." It bridges the gap between Large Language Models (LLMs) and structured databases by generating and managing tailored context. This context helps the LLM understand database schema, business logic, and terminology, enabling more accurate Natural Language to SQL generation.

**Crucially, this server depends on a running MCP Toolbox server for database connection and schema fetching, and relies on Evalbench to execute evaluation workloads.**


## Core Concepts

A `ContextSet` is the central artifact, containing structured knowledge in three primary forms:

- **Templates**: End-to-end mappings linking a natural language query to a complete, runnable SQL query. They teach the system overarching operational logic, table join infrastructures, and broad business rules.
    - *Generation Logic*: Derived from user-approved question-SQL pairs.
    - *Example*:
      ```json
      {
        "nl_query": "How many accounts are in London?",
        "sql": "SELECT count(*) FROM account WHERE city = 'London'",
        "intent": "How many accounts are in London?",
        "manifest": "How many accounts are in a given city?",
        "parameterized": {
          "parameterized_sql": "SELECT count(*) FROM account WHERE city = $1",
          "parameterized_intent": "How many accounts are in $1?"
        }
      }
      ```

- **Facets**: Reusable, modular SQL fragments (like a `WHERE` clause or specialized join). They are not standalone queries but dynamically injected filters linked to specific vocabulary or terminology.
    - *Generation Logic*: Derived from user-approved intents and SQL snippets.
    - *Example*:
      ```json
      {
        "sql_snippet": "rating > 4.5",
        "intent": "highly rated products (above 4.5)",
        "manifest": "highly rated products (above a given number)",
        "parameterized": {
          "parameterized_sql_snippet": "rating > $1",
          "parameterized_intent": "highly rated products (above $1)"
        }
      }
      ```

- **Value Searches**: Specialized queries used when a value in the natural language query (e.g., "Lndn") does not perfectly match the stored value in the database ("London"). They employ mapping functions (like fuzzy trigram matching or semantic similarity) to find candidate values and their distance from the search term.
    - *Generation Logic*: Generated based on table/column definitions and a chosen match function (e.g., `TRIGRAM_STRING_MATCH`).
    - *Example* (Conceptual Fuzzy Match):
      ```json
      {
        "concept_type": "City",
        "query": "SELECT T.\"location\" AS value, 'users.location' AS columns, 'City' AS concept_type, fuzzy_distance(T.\"location\", $value) AS distance FROM \"users\" T WHERE fuzzy_match(T.\"location\", $value)",
        "description": "Fuzzy match for city in location column"
      }

      ```


## Key Workflows

- **Manual Generation**: Targeted, human-driven creation of context. Implemented via MCP prompts for all 3 key context types: `/generate_targeted_templates`, `/generate_targeted_facets`, and `/generate_targeted_value_searches`.
- **Autoctx (Orchestrated)**: Automated, iterative refinement of a ContextSet. The user first runs `/autoctx:setup-db-connection` to create a `tools.yaml`, then `/autoctx:hillclimb` owns the full loop — scaffolding the `autoctx/` workspace on first run, selecting/creating an experiment, invoking the bootstrap and evaluation skills internally, performing gap analysis and mutation, and looping until the user stops.
- **Autoctx (Standalone)**: The setup-db-connection, bootstrap, evaluation, and dataset-generation skills are also invocable directly with explicit path inputs — no `autoctx/` workspace required. Use these for one-off operations (e.g., evaluating against a user-supplied `run_config.yaml`, or bootstrapping a context to an arbitrary file path).


## Workspace Folder Structure

The orchestrated hill-climb loop generates and interacts with a structured workspace to maintain state and trace progress across iterations. This structure is **owned by `skill-hillclimb`** — the standalone skills (bootstrap, evaluate, dataset-generation) do not assume this layout and accept all paths as inputs.

### Directory Layout
- `autoctx/`: The dedicated workspace directory for the orchestrated loop. The `autoctx/` directory itself is created by `skill-setup-db-connection` (to hold the default `tools.yaml`) or by `skill-hillclimb` on first run.
    - `tools.yaml`: Configuration file for the Toolbox MCP Server (defining database connections). Lives here by default because the plugin's bundled toolbox MCP server is hard-coded to load from this path. The user may override and place it elsewhere.
    - `state.md`: High-level summary of the experiment state, active experiment, recorded loop inputs (`tools_config_path`, `dataset_path`, `context_set_id`, etc.), and run history. Created by `skill-hillclimb` on first run.
    - `experiments/`: Root directory for all experiments.
        - `<experiment_name>/`: Specific experiment directory.
            - `bootstrap_context.json`: The baseline ContextSet generated by the Bootstrap skill (when the user chose to bootstrap rather than supply a pre-existing context).
            - `eval_vN/`: Per-iteration evaluation directory created by the orchestrator for loop `vN`.
                - `run_config.yaml`, `db_config.yaml`, `model_config.yaml`, `llmrater_config.yaml`, `golden_queries.json`: Generated Evalbench configurations.
                - Evalbench report folder (location set by `run_config.yaml`'s `output_dir`) containing `scores.csv`, `summary.csv`, etc.
            - `hillclimb/`: Directory containing hill-climbing iteration artifacts.
                - `gap_analysis_vN.md`: Analysis of missing contexts at iteration `N`.
                - `improved_context_vN.json`: The mutated ContextSet at iteration `N`.

> [!NOTE]
> The **simplified golden evaluation dataset** is the **user-facing external format** required as input for the evaluation skill. It can reside anywhere in the file system. The `generate_evalbench_configs` tool automatically converts it into the **EvalBench internal format** and saves it as `golden_queries.json` alongside the generated configs.
>
> See `skills/evaluate/SKILL.md` for details on the simplified user-facing format.


### Workspace Evolution Lifecycle

The workspace folder structure populates progressively as the orchestrator runs:

1. **Pre-requisite (`/autoctx:setup-db-connection`)**:
   - Creates `autoctx/tools.yaml` (default) describing one or more database connections. Creates the `autoctx/` directory if missing.

2. **First call to `/autoctx:hillclimb`** (orchestrator):
   - Scaffolds `autoctx/state.md` and `autoctx/experiments/` if they don't already exist.
   - Confirms `tools_config_path` (defaults to `autoctx/tools.yaml`) and persists it in `state.md`.
   - Creates `autoctx/experiments/<experiment_name>/`.
   - Optionally invokes `skill-bootstrap` to produce `bootstrap_context.json` in the experiment folder (alternatively, the user supplies a pre-existing context path).
   - Records remaining loop inputs (`dataset_path`, `context_set_id`, etc.) in `state.md`.

3. **Each loop iteration `vN`** within `/autoctx:hillclimb`:
   - Invokes `skill-evaluate` with explicit inputs and `output_dir=autoctx/experiments/<name>/eval_vN/`, producing configs and an Evalbench report there.
   - Produces `hillclimb/gap_analysis_vN.md` and `hillclimb/improved_context_vN.json`.
   - Updates `state.md` with the loop's lineage.
   - After upload, captures the new `context_set_id` from the user and either proceeds to `v(N+1)` or stops.

Detailed specifications for files used or generated by a skill are kept within that specific skill's `SKILL.md` file.


## ContextSet Management Tools

Use the `mutate_context_set` tool for all ContextSet changes. It supports granular additions, updates, and deletions of ContextSet items without replacing the whole file. Pass mutation payloads directly — the tool handles all file I/O internally, so the agent should not read the target file beforehand.

## Handling API Errors

> [!IMPORTANT]
> If you encounter a `503` or `429` error, or an `UNAVAILABLE` or `RESOURCE_EXHAUSTED` status code from any tool (indicating the backend model is experiencing high demand or rate limiting), you **MUST** stop attempting alternative solutions or workarounds. Report the failure directly to the user immediately. Do not try to call other tools or guess results when the model is unavailable.
