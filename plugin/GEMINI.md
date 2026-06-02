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
- **Autoctx**: Four goal-oriented skills that compose freely. They are not a fixed pipeline — each is independently usable:
    - `/autoctx:init` — configure a Toolbox `tools.yaml` for a database connection.
    - `/autoctx:bootstrap` — generate a baseline ContextSet from a DB schema; outputs a local JSON file; optionally uploads to the Context Store.
    - `/autoctx:eval` — score any uploaded ContextSet against a golden dataset on any configured DB. Takes a `context_set_id` (resource name); does not care how the ContextSet was authored.
    - `/autoctx:hillclimb` — iterative auto-improvement loop. Composes the other three internally and owns the only stateful workspace. Resumable across sessions.


## Skill composition and the Context Store

The handoff between skills is the **Context Store resource name** (eg. `projects/<p>/locations/<l>/contextSetGroups/<csg>/contextSets/<cs>@<version>`), not a filesystem path. The flow:

1. `bootstrap` produces a local ContextSet file, then optionally calls the `upload_context_set` MCP tool to push it to the Context Store. The tool returns the resource name.
2. `eval` takes the resource name and runs EvalBench against it.
3. `hillclimb` orchestrates the above plus its own mutation loop, uploading each new version under a stable `(csg_id, cs_id)` with incrementing `version` labels (`v0`, `v1`, ...).

The Context Store protocol (ContextSetGroup-before-ContextSet, LRO polling, version semantics) is hidden inside the `upload_context_set` MCP tool. Skills never construct resource names by hand.

> [!NOTE]
> The **simplified golden evaluation dataset** is the **user-facing external format** required as input for evaluation. It can reside anywhere in the file system. `generate_evalbench_configs` converts it to the EvalBench internal format automatically.
>
> See `skills/autoctx-evaluate/SKILL.md` for the schema.


## Workspaces

The autoctx skills do **not** share a workspace.

- `init` writes a single `tools.yaml` to a caller-supplied path (defaults to cwd). After any change, the Toolbox MCP server must be restarted (`/reload-plugins` in Claude Code, `/mcp reload` in Gemini CLI).
- `bootstrap` writes one local JSON file to a caller-supplied path.
- `eval` writes its artifacts to a caller-supplied directory (default: `./eval-runs/<experiment>/`).
- `hillclimb` owns the only stateful workspace, default path `./autoctx-experiment/<experiment_name>/`. It is internal to the skill — other skills do not read or write it. The layout (`vN/`, `state.md`) is a reference convention that can be swapped (eg. for git-based versioning) without affecting the skill's contract.

There is no global `autoctx/` directory and no shared `state.md`. The previously documented `autoctx/experiments/` hierarchy is removed.


## ContextSet Management Tools

Use the `mutate_context_set` tool for all ContextSet changes. It supports granular additions, updates, and deletions of ContextSet items without replacing the whole file. Pass mutation payloads directly — the tool handles all file I/O internally, so the agent should not read the target file beforehand.

## Handling API Errors

> [!IMPORTANT]
> If you encounter a `503` or `429` error, or an `UNAVAILABLE` or `RESOURCE_EXHAUSTED` status code from any tool (indicating the backend model is experiencing high demand or rate limiting), you **MUST** stop attempting alternative solutions or workarounds. Report the failure directly to the user immediately. Do not try to call other tools or guess results when the model is unavailable.
