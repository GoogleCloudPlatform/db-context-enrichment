---
name: context-engineering-init
description: Ensure the environment is ready for context-engineering work — manage the Toolbox `tools.yaml` for database connections, verify runtime and GCP setup (uv, evalbench, ADC, Dataplex/GDA APIs, IAM), and diagnose readiness failures raised by other skills.
---

# Skill: Environment & Connection Setup

## Goal
Ensure the caller's environment is ready for context-engineering work: Toolbox `tools.yaml` in place with at least one verified DB source, and (when asked or when downstream failures need diagnosis) runtime + GCP readiness verified. Manage `tools.yaml` on request; run any subset of checks on request.

## Prerequisites
- `gcloud` CLI on PATH.
- (Optional) Target GCP project id — if not provided, use ADC's default project.
- (Optional) Existing `tools.yaml` to amend rather than overwrite.

## Guidance

Pick the flow that matches the user's intent:

### Manage `tools.yaml` (DB connections)

Three sub-workflows:

**Create new**
1. Identify the DB type; load `references/<db_type>.md` for required fields.
2. Ask the user for every required field explicitly. Do not fill in missing values.
3. Generate the YAML from the template with the user's values.
4. Save to `.context-engineering/tools.yaml`. This path is fixed — the Toolbox MCP server reads it directly; any other path won't be picked up.

**Add to existing**
1. Identify the new DB type and a unique `<source>` name.
2. Ask for the required fields (same as Create).
3. Read the current `tools.yaml`.
4. Generate new `sources:` and `tools:` entries under the unique `<source>` name and append them.
5. Save the updated file.

**List existing**
1. Read the `tools.yaml` at the given path. If missing, tell the user.
2. Parse and list all names under `sources:`.

Validate the target source(s) standalone (Example: `uvx toolbox-server@1.4.0 --config <path> invoke <source>-list-schemas`) — no MCP restart needed for validation. On validation failure, drop into the checks below to diagnose (e.g., `DB source reachable`, `ADC configured`).

After any write, instruct the user to restart the MCP server so downstream skills see the new source:
- Gemini CLI: `/mcp reload`
- Claude Code: `/mcp` → `toolbox` → Reconnect (or `/quit` and relaunch)
- Antigravity CLI: `/mcp` → `toolbox` → Restart

### Verify environment (broad or scoped)

Run any subset of the checks below. Report `PASS` or `FAIL` per check. For any `FAIL`, propose a fix and ask the user for consent before executing anything mutating (installing packages, enabling APIs, changing IAM, writing files).

- **Broad verification** ("am I ready?") → run all checks.
- **Scoped diagnosis** (a downstream skill failed) → run only the checks whose `— required by …` line references the failing operation.

## Checks

Commands in parentheses are examples — the agent may use its own approach.

### Environment
- **`uv` installed** — required to run Toolbox and Evalbench via `uvx`. (Example: `uv --version`; install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.)
- **Evalbench reachable** — required by `context-engineering-evaluate`; verifying also warms the uvx cache so the first `evaluate` run is fast. (Example: `uvx google-evalbench@1.10.0 --help`.)

### GCP authentication
- **ADC configured** — required by every GCP API call (Context Store, QueryData, Dataplex). (Example: `gcloud auth application-default print-access-token`; fix via `gcloud auth application-default login`.)
- **ADC quota project set** — required by Context Store; the `X-Goog-User-Project` header is derived from it. Missing → 400 on upload/download. (Example: `gcloud auth application-default print-quota-project`; fix via `gcloud auth application-default set-quota-project <project>`.)

### GCP API enablement
- **Dataplex API** (`dataplex.googleapis.com`) — required by Context Store operations (`upload_context_set`, `download_context_set`).
- **Gemini Data Analytics API** (`geminidataanalytics.googleapis.com`) — required by QueryData (used inside `context-engineering-evaluate`).

(Example: check enablement via `gcloud services list --enabled --project=<project>`; enable via `gcloud services enable <api> --project=<project>`.)

### GCP IAM (operational probes)
- **Context Store access** — required by `upload_context_set` / `download_context_set` and by QueryData's context lookup. Probe by attempting a Dataplex Context Store read (e.g., list CSGs in `<project>`). On 403, surface the error verbatim and ask the user to request the appropriate Context Store role from their IAM admin.
- **GDA access** — required by QueryData (used by `evaluate`). Probe by attempting a lightweight QueryData call in `<project>`. On 403, same handling.

### Toolbox configuration
- **`tools.yaml` present** — required by every skill that reads database schemas (`bootstrap`, `evaluate`, `hillclimb`). Check `.context-engineering/tools.yaml` (the fixed path the Toolbox MCP server reads). Missing → run the Create sub-workflow above.
- **DB source reachable** — required by any Toolbox invocation on that source. For each configured `<source>` in `tools.yaml`, verify Toolbox can list its schemas standalone. On failure, surface the error verbatim; common causes are ADC, wrong project/region, DB IAM, or network. (Example: `uvx toolbox-server@1.4.0 --config <path> invoke <source>-list-schemas`.)

## Rules
- Never execute mutating actions (`gcloud services enable`, `gcloud projects add-iam-policy-binding`, package installs, file writes) without explicit user consent — surface the exact command and let the user run it, or ask consent before running.
- ADC only for DB auth. Never write username/password into `tools.yaml`.
- `tools.yaml` always lives at `.context-engineering/tools.yaml` — do not offer or accept a different path. If the file exists, ask whether to append or overwrite.
- Do not guess DB connection details. Ask the user for every required field explicitly.

## Credentials message (use when collecting DB info for `tools.yaml`)

> "I'll help you configure the database connection in `tools.yaml`. The Toolbox server uses Application Default Credentials (ADC) for authentication, so you don't need to provide a username or password. Please ensure the IAM account you're using has the required permissions to access the database.
>
> Could you please provide the following details:
> - Google Cloud Project ID:
> - Region:
> - ... (other required fields based on database type)"

## References
- `references/<db_type>.md` (`alloydb-postgres.md`, `cloud-sql-mysql.md`, `cloud-sql-postgres.md`, `spanner.md`) — per-DB required fields and YAML template.

## Gotchas
- **Quota project vs ADC project:** ADC infers a default project from `gcloud config`, but Context Store requires an explicit quota project via `X-Goog-User-Project`. Missing quota project → 400 from Context Store API.
- **MCP restart required for new tools.yaml sources:** Toolbox reads `tools.yaml` at MCP-server startup. Validation runs standalone, but agent visibility of new sources needs a restart.
- **AlloyDB requires `cluster` + `instance`; Cloud SQL only `instance`.**
- **Spanner uses ADC; verification fails without `gcloud auth application-default login`.**
- **Evalbench cold-cache:** first `uvx google-evalbench@1.10.0` can take minutes to download; verifying `Evalbench reachable` warms the cache so downstream `evaluate` runs are fast.
