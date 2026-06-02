---
name: skill-autoctx-bootstrap
description: Generate a baseline ContextSet (templates, facets, value searches) for a database from its schema. Standalone; output is a local JSON file with optional upload to the Context Store.
---

# Auto Context Bootstrap

## Goals

Produce a baseline `ContextSet` JSON file for a target database, derived from its schema and any user-supplied design docs or application code. Optionally upload it to the Context Store and return a resource name.

## Prerequisites

- A `tools.yaml` with the target database configured as a Toolbox source. If missing, refer the user to the `skill-autoctx-init` skill and stop.
- The Toolbox MCP server is running and exposes `<source>-list-schemas` (and related tools) for the target source. If a recent `tools.yaml` change has not been reloaded, instruct the user to restart the MCP server first.
- Target database name and Toolbox source name (the user provides both, or you confirm from `tools.yaml`).

## Guidances

The skill is one linear pass; do not assume a fixed workspace layout.

1. **Confirm scope.** Ask the user:
   - Which Toolbox source in `tools.yaml` to target (confirm by listing what you find in the file).
   - Output file path for the generated ContextSet. Default: `./<source_name>_bootstrap_context.json` in the cwd. State the absolute path back before writing.
   - Any schema or table filters they want to apply.
2. **Fetch the schema** using `<source>-list-schemas` (and any related Toolbox tools). Present a clean summary back to the user — schemas, tables, key columns. Ask whether to narrow further.
3. **Collect enrichment sources.** Ask the user if they want to provide design docs, ORM models, sample SQL, or business glossary. Wait for response. If they decline, proceed with schema only.
4. **Identify candidates.** From schema + any supplied docs, surface:
   - Representative NL → SQL pairs that exercise common query patterns and joins (→ Templates).
   - Recurring filter conditions or business rules (→ Facets).
   - Columns whose values are likely to need fuzzy / semantic matching from user input (→ Value Searches).
5. **Review with the user.** Briefly list the candidates and confirm before generation. Trim aggressively if the list is overlong — quality beats coverage at the baseline.
6. **Generate the ContextSet.** Invoke the `context-generation-guide` skill with the approved candidates. It handles parameterization, dialect specifics, and the JSON shape.
7. **Write the file.** Initialize an empty ContextSet JSON at the output path, then use `mutate_context_set` with one `"operation": "add"` per generated item (Template, Facet, Value Search).
8. **Optional upload.** Ask the user if they want to push the file to the Context Store now. If yes:
   - Ask for a `csg_id` (suggest the source name as a default — `<source_name>`).
   - Use `cs_id="autoctx"` and `version="baseline"` as defaults; let the user override.
   - Call `upload_context_set(local_file_path, csg_id, cs_id, version)`. Surface the returned resource name to the user.
   - On a 409 error (version already exists), ask whether to bump the version label rather than silently overwriting.
9. **Summarize.** Report the local file path and (if uploaded) the resource name. Do not invoke evaluate or hillclimb — those are the user's next move.

## Rules

- **Never write to `autoctx/experiments/...` or any fixed path.** The caller supplies (or confirms a default for) the output path.
- **Never upload without the user's explicit consent in step 8.** Local file is the default output.
- **Never overwrite an existing ContextSet version in the Context Store.** A 409 surfaces to the user; bump the version label rather than retry blindly.
- **Do not invoke `skill-autoctx-evaluate` or `skill-autoctx-hillclimb`.** Bootstrap returns; the user composes the next step.

## Tools

- **`<source>-list-schemas`** (Toolbox MCP) — and related schema-introspection tools — to fetch DB metadata.
- **`mutate_context_set`** (MCP) — to write generated items into the output file.
- **`upload_context_set`** (MCP) — optional, when the user wants to push to the Context Store. Returns the full resource name.
- **`skill-context-generation-guide`** — invoked to produce well-formed Template / Facet / ValueSearch JSON from the candidates.
- **Read / Write** — to read `tools.yaml`, initialize the output JSON, and inspect user-supplied docs.
