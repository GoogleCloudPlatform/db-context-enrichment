# Environment Verification Checks & Troubleshooting Gotchas

> **Parent Skill Reference**: This reference contains the detailed diagnostic checks and troubleshooting gotchas for [`context-engineering-init`](../SKILL.md). Run any subset of checks below (report `PASS` or `FAIL` per check, and ask user consent before executing mutating actions).

## Checks

Commands in parentheses are examples — the agent may use its own approach.

### Environment
- **`uv` installed** — required to run Toolbox and Evalbench via `uvx`. (Example: `uv --version`; install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.)
- **Evalbench reachable** — required by `context-engineering-evaluate`; verifying also warms the uvx cache so the first `evaluate` run is fast. (Example: `uvx google-evalbench@1.19.0 --help`.)

### GCP authentication
- **ADC configured** — required by every GCP API call (Context Set server, QueryData, Dataplex). (Example: `gcloud auth application-default print-access-token`; fix via `gcloud auth application-default login`.)
- **ADC quota project set** — required by Context Set server; the `X-Goog-User-Project` header is derived from it. Missing → 400 on upload/download. (Example: check `quota_project_id` in `~/.config/gcloud/application_default_credentials.json`, e.g. `python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/gcloud/application_default_credentials.json'))).get('quota_project_id'))"`; fix via `gcloud auth application-default set-quota-project <project>`.)

### GCP API enablement
- **Dataplex API** (`dataplex.googleapis.com`) — required by every Context Set tool (`list_context_set_locations`, `upload_context_set`, `get_context_set`, `delete_context_set`, `get_operation`). See the Context Set MCP Protocol in `context-engineering-workflow` ([`ctxset-mcp-protocol.md`](../../context-engineering-workflow/references/ctxset-mcp-protocol.md)) for how these are used.
- **Gemini Data Analytics API** (`geminidataanalytics.googleapis.com`) — required by QueryData (used inside `context-engineering-evaluate`).

(Example: check enablement via `gcloud services list --enabled --project=<project>`; enable via `gcloud services enable <api> --project=<project>`.)

### GCP IAM (operational probes)
- **Context Set server connected** — the five Context Set tools (`list_context_set_locations`, `upload_context_set`, `get_context_set`, `delete_context_set`, `get_operation`) are served by the **remote Context Set MCP server** registered in the plugin manifests under the key `ctxset` (Google-credentials auth). Check that all five appear in your tool list. If they do not, do not continue the preflight: tell the user the remote server is not connected and give the fix — ADC present with a quota project (checks above), then reload MCP servers in the client (Antigravity: open the MCP panel; Gemini CLI: `/mcp refresh`). A `401`/`UNAUTHENTICATED` on the first call to any of these tools means the client could not mint an ADC token: re-run `gcloud auth application-default login`, then reload.
- **Context Set access** — required by every Context Set tool and by QueryData's context lookup. Probe by calling `get_context_set(projectId=<project>, location=<location>, contextSetId=preflight-probe-does-not-exist)` in the chosen `<location>` (or `us-central1` if not yet chosen) — a well-formed identity that is known not to exist. Interpret the outcome:
  - **NOT_FOUND** (including plain text `"Resource was not found."` in `content[0].text` with `isError: true`) → the request was authenticated and authorized and reached the API; the probe **passes**. This is the expected result.
  - **UNAUTHENTICATED** → ADC is missing or expired; point the user back to the GCP authentication checks above.
  - **PERMISSION_DENIED** → surface the error verbatim and ask the user to request the appropriate Context Set IAM role from their IAM admin.
  - Anything else → surface the error verbatim; do not guess at the cause.
- **GDA access** — required by QueryData (used by `evaluate`). Probe by attempting a lightweight QueryData call in `<project>`. On 403, same handling.

### Workspace files
- **`tools.yaml` present** — required by every skill that reads database schemas (`bootstrap`, `evaluate`, `hillclimb`). Check `.context-engineering/tools.yaml` (the fixed path the Toolbox MCP server reads; on Antigravity, also verify that `~/.gemini/config/plugins/<matched_plugin_name>/.context-engineering` symlinks to `<absolute_workspace_path>/.context-engineering` per the Antigravity restart note in [`SKILL.md`](../SKILL.md) — if it is missing or points to another workspace, update the symlink and ask the user to restart `toolbox`). Missing → run the Create sub-workflow in [`SKILL.md`](../SKILL.md).
- **`workspace_state.md` present and complete** — required by every skill that starts or resumes an experiment. Check `.context-engineering/workspace_state.md` has `Project`, `Location`, `Default DB source`, `Auto-approve uploads` (enrichment sources may be `(none)`), that `Default DB source` names a source in `tools.yaml`, and that `Location` is still in `list_context_set_locations(Project)`. Missing → run **Record the workspace inputs** in [`SKILL.md`](../SKILL.md); incomplete → ask only for the missing bullets.
- **Toolbox server in sync with `tools.yaml`** — required for the agent to see the sources. For every `kind: source` in `tools.yaml`, the corresponding `<source>-list-schemas` / `<source>-execute-sql` tools must be present in the agent's tool list. Any source present in the file but absent from the tool list → the server was started before that source was added (or the user edited the file by hand): **tell the user to restart the `toolbox` MCP server** (instructions in [`SKILL.md`](../SKILL.md)) and re-check.
- **Experiment source still configured** — required by every skill running inside an experiment. The **Source Name** under `## Active Database` in the experiment's `experiment_state.md` must exist in `tools.yaml`. Missing → the user removed or renamed it; ask them to restore it (or add it back via the Add sub-workflow) rather than silently picking another source.
- **DB source reachable** — required by any Toolbox invocation on that source. For each configured `<source>` in `tools.yaml`, verify Toolbox can list its schemas standalone. On failure, surface the error verbatim; common causes are ADC, wrong project/region, DB IAM, or network. (Example: `uvx toolbox-server@1.14.0 --config .context-engineering/tools.yaml invoke <source>-list-schemas`.)

---

## Gotchas
- **Quota project vs ADC project:** ADC infers a default project from `gcloud config`, but Context Set server requires an explicit quota project via `X-Goog-User-Project`. Missing quota project → 400 from Context Set API.
- **Context Set uploads and deletes are asynchronous:** `upload_context_set` / `delete_context_set` return an operation, not a finished result. Downstream skills must poll `get_operation(projectId, location, operationId)` until `done: true`, waiting ≥5 s between polls (see the Context Set MCP Protocol in `context-engineering-workflow`). The preflight probe above uses `get_context_set`, which is synchronous, precisely so it needs no polling.
- **Context Set endpoint lives in the plugin manifests, not in `tools.yaml`:** the remote server URL is the `ctxset` entry in `plugin/mcp_config.json` / `gemini-extension.json`. A probe that fails with a connection or DNS error points at that URL or at the client's MCP configuration, not at the user's `tools.yaml`. The client mints the bearer token from ADC and sets `X-Goog-User-Project` from the ADC quota project, which is why the quota-project check above matters.
- **MCP restart required whenever `tools.yaml` changes — by this skill or by the user:** the `toolbox` MCP server reads `.context-engineering/tools.yaml` only at startup. Standalone validation (`uvx toolbox-server … invoke`) sees the new file immediately, which makes the stale server easy to miss. Symptoms: a source that is in `tools.yaml` has no `<source>-list-schemas` tool, or a tool still reflects a connection value that the user has since edited. Fix: restart the `toolbox` server with the per-client instructions in [`SKILL.md`](../SKILL.md), then re-run the *Toolbox server in sync* check.
- **AlloyDB requires `cluster` + `instance`; Cloud SQL only `instance`.**
- **Spanner uses ADC; verification fails without `gcloud auth application-default login`.**
- **Evalbench cold-cache:** first `uvx google-evalbench@1.19.0` can take minutes to download; verifying `Evalbench reachable` warms the cache so downstream `evaluate` runs are fast.
