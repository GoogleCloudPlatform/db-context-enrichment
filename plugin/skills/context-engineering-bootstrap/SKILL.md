---
name: context-engineering-bootstrap
description: Generate a baseline ContextSet (Templates, Facets, Value Searches) from a target database's schema (and optional design docs / application code) and save to a caller-specified path. Optionally upload to the Context Store.
---

> **Load [`context-engineering-workflow`](../context-engineering-workflow/SKILL.md) first** for shared terminology, lifecycle overview, and safety protocol.

# Skill: Baseline ContextSet Bootstrapping

## Goal
From a target database and optional user-supplied enrichment sources (design docs, ORM models, sample SQL, glossary), produce a baseline `ContextSet` JSON at a caller-specified path. Optionally upload to the Context Store and return the resource name.

## Prerequisites
- A working DB connection — Toolbox MCP tools (`<source>-list-schemas`) must be visible to the agent throughout the run. If missing or unreachable at any point, stop and route through `context-engineering-init`; do not work around it (no bash `uvx toolbox-server invoke` fallback).
- Target output path for the ContextSet JSON. If not supplied, prompt the user; default `./bootstrap_context.json` at cwd.
- (Optional) Design docs, application code, sample SQL, glossary, or other enrichment sources.
- (Optional, for upload) Context Store resource coordinates — see the `upload_context_set` tool for required fields.

## Guidance

1. **Confirm scope with the user:**
   - Which Toolbox `<source>` to introspect (auto-select if exactly one supported source exists in `tools.yaml`; otherwise prompt).
   - Which schemas / tables to focus on (or all, if the DB is small).
   - Output path for the ContextSet JSON.
   - Whether to upload to Context Store after generation; if yes, collect the resource coordinates required by `upload_context_set`.

2. **Fetch the schema:** use `<source>-list-schemas` (and related introspection tools). Present the schema summary structurally to the user.

3. **Collect enrichment sources:** prompt for design docs, ORM models, sample SQL, glossary, etc. Wait for the user's response before proceeding.

4. **Identify candidate items:** analyze schema + enrichment to identify representative NLQ + SQL pairs (Templates), common filter fragments (Facets), and columns needing fuzzy/semantic matching (Value Searches). Present the candidates to the user for review before generating.

5. **Generate the ContextSet:** invoke the `context-engineering-generation-guide` skill with the approved candidates. Save items incrementally to the output path via the `mutate_context_set` MCP tool. For a new file, construct `"operation": "add"` mutations for each item.

6. **Optionally upload:** if the user opted to upload, call `upload_context_set`.

7. **Summarize:** report the local file path and (if uploaded) the resource name.

## Rules
- Caller supplies (or explicitly confirms a default for) the output path.
- Never upload without explicit user consent.
- Always use the `mutate_context_set` MCP tool for ContextSet file changes — pass mutation payloads directly. Do not read the target file beforehand.
- Do not invoke `context-engineering-evaluate` or `context-engineering-hillclimb`.

## Tools

**MCP:**
- `<source>-list-schemas` (Toolbox) — schema introspection.
- `mutate_context_set` — incremental writes to the output JSON.
- `upload_context_set` → `cs_resource_name` — optional Context Store upload.

**Sibling skill:**
- `context-engineering-generation-guide` — produces well-formed Template / Facet / Value Search JSON. Also the reference for context-item schema and authoring standards.
