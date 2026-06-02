---
name: skill-autoctx-init
description: Configure a Toolbox `tools.yaml` so downstream skills (bootstrap, evaluate, hillclimb) can talk to a database. Standalone — no workspace scaffolding.
---

# Auto Context Init: Database Connection Setup

## Goals

Produce a working `tools.yaml` with at least one verified Toolbox data source. Other autoctx skills consume `tools.yaml` by path; this skill does not create any other files.

## Prerequisites

- The user knows their database connection details (project, region, instance/cluster, database name).
- For Google Cloud databases: Application Default Credentials are configured (`gcloud auth application-default login`) and the ADC identity has IAM access to the database. Username/password auth is not supported.

## Guidances

> All `references/...` paths below are bundled with this skill, alongside this `SKILL.md`.

Three sub-workflows. Pick the one matching the user's request.

### 1. Create a new `tools.yaml`

1. **Confirm the target path.** Ask the user where the file should be written. Default to `tools.yaml` in the current working directory. State the absolute path back to the user before writing.
2. **Identify the database type.** One of: Cloud SQL Postgres, Cloud SQL MySQL, AlloyDB Postgres, Spanner.
3. **Collect the required fields.** Use the matching template in `references/` to identify all required fields. Ask the user explicitly for each; do not guess. Tell them ADC handles auth, so no username or password is needed.
4. **Write the file.** Fill the template, write to the confirmed path.
5. **Validate the source.** Run `npx -y @toolbox-sdk/server --config <config_path> invoke <data_source_name>-list-schemas`. If it fails, surface the error and help the user diagnose (wrong project, missing IAM permission, instance not running).
6. **Tell the user to restart the MCP server** (see Rules below).

### 2. Add a database source to an existing `tools.yaml`

1. Read the existing file.
2. Collect the new source's required fields, including a unique `<data_source_name>`.
3. Append the new entries under `sources:` and `tools:`.
4. Validate only the new source with the same `invoke` command.
5. Tell the user to restart the MCP server.

### 3. List existing database sources

1. Read `tools.yaml`.
2. List the names under `sources:`. If the file is missing, tell the user and offer to run workflow 1.

## Rules

- **Always confirm the target path before writing.** The user may already have a `tools.yaml` elsewhere; never assume a fixed location.
- **Never write credentials into `tools.yaml`.** Only ADC is supported. If the user offers a password, refuse and explain.
- **After any change to `tools.yaml`, the Toolbox MCP server must be restarted** for the new source to become visible to other tools. Instruct the user explicitly and wait for confirmation before declaring success:
  - **Claude Code**: `/reload-plugins`
  - **Gemini CLI**: `/mcp reload`
- **Do not create `autoctx/`, `state.md`, `experiments/`, or any other directories.** This skill owns `tools.yaml` only. Hillclimb owns workspace lifecycle.

## Tools

- **Bash** — to run the Toolbox validation command (`npx -y @toolbox-sdk/server ... invoke <name>-list-schemas`).
- **Read / Write** — to read existing `tools.yaml` and write a new one.
- `references/{alloydb-postgres,cloud-sql-postgres,cloud-sql-mysql,spanner}.md` — per-database-type field templates. Treat as authoritative for required fields.
