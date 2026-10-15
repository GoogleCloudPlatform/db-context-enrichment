---
name: context-engineering-bootstrap
description: Generate a baseline ContextSet (Templates, Facets, Value Searches) from a target database's schema (and optional design docs / application code) and save to a caller-specified path. Optionally upload to the Context Set server.  Don't use when a user asks to build, validate, or improve a context set from scratch end-to-end (use `context-engineering-workflow` instead).
---

> **Load [`context-engineering-workflow`](../context-engineering-workflow/SKILL.md) first** for shared terminology, lifecycle overview, and safety protocol. If the user is asking to build a context set from scratch (end-to-end with evaluation and optimization), route through `context-engineering-workflow` (`init` $\rightarrow$ `dataset-generation` $\rightarrow$ `hillclimb`) rather than running standalone bootstrap.

# Skill: Baseline ContextSet Bootstrapping

## Goal
From a target database and optional user-supplied enrichment sources (design docs, ORM models, sample SQL, glossary), produce a baseline `ContextSet` JSON at a caller-specified path. Optionally upload to the Context Set server and return the resource name.

## Prerequisites
- A working DB connection — Toolbox MCP tools (`<source>-list-schemas`) must be visible to the agent throughout the run. If missing or unreachable at any point, stop and route through `context-engineering-init`; do not work around it (no bash `uvx toolbox-server invoke` fallback).
- Target output path for the ContextSet JSON. If not supplied, prompt the user; default `./bootstrap_context.json` at cwd.
- (Optional) Design docs, application code, sample SQL, glossary, or other enrichment sources.
- (Optional, for upload) The target Context Set resource: `projectId`, `location`, and a `contextSetId` (project and location default to `.context-engineering/workspace_state.md` when it exists). Together they form `projects/<project_id>/locations/<location>/contextSets/<context_set_id>` — see the Context Set (OneMCP) Protocol in `context-engineering-workflow`.

**When invoked by `context-engineering-hillclimb` inside an experiment** (`.context-engineering/experiments/<experiment_name>/hillclimb/experiment_state.md` exists): read the Toolbox source from `experiment_state.md ## Active Database` and the enrichment sources per *Inputs & resolution rules* in `context-engineering-workflow` (`Enrichment sources (this experiment)` in `experiment_state.md` if present, otherwise `Enrichment sources` in `.context-engineering/workspace_state.md`), write the output to `.context-engineering/experiments/<experiment_name>/hillclimb/v0/context_set_v0.json`, skip steps 1–2 below unless a value is missing from both files, **run steps 3–6 autonomously without pausing for interactive schema or candidate approval** (the hill-climb loop's `Auto-approve uploads` setting governs whether `v0` pauses before upload), and **do not upload** — the hill-climb loop owns all uploads.

## Guidance

1. **Confirm scope with the user (standalone only):**
   - Which Toolbox `<source>` to introspect (default: `Default DB source` in `.context-engineering/workspace_state.md` when it exists; else auto-select if exactly one supported source exists in `tools.yaml`; otherwise prompt).
   - Which schemas / tables to focus on (or all, if the DB is small).
   - Output path for the ContextSet JSON.
   - Whether to upload to Context Set server after generation. If yes, take `projectId` and `location` from `.context-engineering/workspace_state.md` when it exists (show them; ask only if missing or the user wants different ones) and ask for `contextSetId`; call `list_context_set_locations(projectId)` and confirm the chosen location is in the returned list (if not, let the user pick one from it). Tell the user the exact resource name that will be written.

2. **Collect enrichment sources (standalone only):** default to `Enrichment sources` in `.context-engineering/workspace_state.md` when it exists (show them and ask whether to add more for this run); otherwise prompt for design docs, ORM models, sample SQL, glossary, etc. Wait for the user's response before proceeding.

3. **Deduce Key Info (Core Execution):**
   - **Targeted Schema & Graph Retrieval**: Informed by the ingested application artifacts and design docs, use the available Toolbox MCP tools (e.g., `<source>-list-schemas`, `<source>-list-graphs`) to fetch the schemas for the target database and relevant tables/graphs. The sources come from the shared `.context-engineering/tools.yaml`; inside an experiment, use the **Source Name** (and its listed **Tools**) recorded under `## Active Database` in the experiment's `experiment_state.md` rather than picking a source ad hoc.
   - **Standalone only:** Present the retrieved schema summary **structurally and cleanly** to the user and ask if they want to filter or focus on specific schemas, tables, or graphs. (Inside `hillclimb`, proceed directly using the experiment's active database scope.)
   - Perform a **deep analysis** of the retrieved **schema and any provided documentation or code** to identify important concepts, relationships, and likely query patterns.
   - **GQL Preference for Graph Entities**: When querying entities or relationships that are modeled within a property graph, **always prefer GQL (`GRAPH <graph_name> MATCH ...`)** over writing relational SQL `JOIN` queries against the underlying node/edge tables.

4. **Identify candidate items:** analyze schema + enrichment to identify representative natural language queries with their corresponding SQL/GQL (Templates), common filter conditions or business rules and graph pattern fragments (Facets), and columns that require specialized fuzzy/semantic value searching (Value Searches). **In standalone mode**, present these candidates to the user for review and approval before generating; **when invoked by `hillclimb`**, proceed directly to step 5.

5. **Generate the ContextSet:** invoke the `context-engineering-generation-guide` skill with the approved candidates. Save items incrementally to the output path via the `mutate_context_set` MCP tool. For a new file, construct `"operation": "add"` mutations for each item.

6. **Validate**: Call `validate_context_set` on the output file. If invalid, fix each issue via `mutate_context_set` and re-validate until clean. Stop after two failed attempts and surface remaining issues to the user.

7. **Optionally upload:** if the user opted to upload:
   - Form the target resource name from `projectId`, `location`, `contextSetId` per the **Resource naming rule** in `context-engineering-workflow` and show it to the user. Remind them that if a context set with this name already exists, the upload **overwrites it** and the previous contents cannot be recovered; proceed only on explicit confirmation.
   - Read the validated output file and call `upload_context_set(projectId=<project_id>, location=<location>, contextSetId=<context_set_id>, contextPayload=<exact file contents>, description=<short description>, databases=<Database>)` — `<Database>` is derived at upload time from the experiment's `## Active Database` **Source Name** (standalone: the chosen source) and that source's block in `tools.yaml`, using the mapping table under *Database association* in `context-engineering-workflow`, sent in the wire shape the live schema accepts (object list or URI-string list — see that section).
   - Poll `get_operation(projectId, location, operationId)` on the returned operation (≥5 s between polls, 5-minute ceiling) until `done: true` before continuing — see the Context Set (OneMCP) Protocol in `context-engineering-workflow`. On `done: true` the upload is complete; on an `error` field, surface it verbatim and stop.

8. **Summarize:** report the local file path and (if uploaded) the resource name and the operation name that completed.

## Rules
- Caller supplies (or explicitly confirms a default for) the output path.
- Never upload without explicit user consent.
- Always use the `mutate_context_set` MCP tool for ContextSet file changes — pass mutation payloads directly. Do not read the target file beforehand.
- Do not invoke `context-engineering-evaluate` or `context-engineering-hillclimb`.

## Tools

**MCP:**
- `<source>-list-schemas` (Toolbox) — schema introspection.
- `mutate_context_set` — incremental writes to the output JSON.
- `list_context_set_locations` (remote Context Set server) — confirm the upload location before uploading.
- `upload_context_set` (remote Context Set server) — optional Context Set server upload; takes the file contents inline in `contextPayload`; returns an operation.
- `get_operation` (remote Context Set server) — poll the upload operation until `done: true`.
- `validate_context_set` — check the output file before uploading.

**Sibling skill:**
- `context-engineering-generation-guide` — produces well-formed Template / Facet / Value Search JSON. Also the reference for context-item schema and authoring standards.
