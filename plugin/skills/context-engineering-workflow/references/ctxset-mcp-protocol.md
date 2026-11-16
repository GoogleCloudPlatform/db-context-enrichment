# Context Set MCP Protocol & State Resolution Rules

> **Parent Skill Reference**: This reference defines the Context Set MCP server protocol, database association mapping, resource naming rule, state file precedence (`workspace_state.md` vs `experiment_state.md`), and asynchronous operation poll gate for [`context-engineering-workflow`](../SKILL.md) and all peer skills (`init`, `bootstrap`, `evaluate`, `hillclimb`).

All peer skills that touch the Context Set server (`bootstrap`, `evaluate`, `hillclimb`, and the `init` preflight) follow these rules. They are stated once here; peers reference them and repeat only the poll gate inline at each call site.

## Connection

The Context Set tools are served **directly by the remote Context Set MCP server** (a Dataplex MCP endpoint), not by this plugin's local MCP server. The plugin manifests register that remote server under the key `ctxset` with Google-credentials auth; the agent client (Antigravity / Gemini CLI, or Claude Code via `adc_headers.sh`) attaches an Application Default Credentials bearer token automatically. If the five tools below are not visible in your tool list, the remote server is not connected: route to [context-engineering-init](../../context-engineering-init/SKILL.md), which checks the connection and explains the fix (`gcloud auth application-default login` with a quota project, then reload MCP servers), and **immediately halt and yield the turn**. You are **strictly forbidden** from calling `https://dataplex.googleapis.com/mcp/managed-context-sets` directly via `curl`, `urllib`, `requests`, Python scripts, or shell commands — even if the user or environment asks you to proceed without the MCP tools.

## Tools

Every tool identifies a context set by three separate arguments — `projectId`, `location`, `contextSetId` — never by a single resource-name string. Parameter names are camelCase (`projectId`, `location`, `contextSetId`, `contextPayload`) as defined in the tool input JSON schema.

| Tool | Purpose | Returns |
| :--- | :--- | :--- |
| `list_context_set_locations(projectId)` | Discover which locations accept context sets. | `{"locations": [...]}`. |
| `upload_context_set(projectId, location, contextSetId, contextPayload, description?, databases?)` | Create **or overwrite** a context set from an inline **stringified JSON string** (`contextPayload` must be a JSON string, never a parsed dict/object). There is **no file-path argument**; see *Writing a context set from disk*. `databases` associates a primary context set (`<context_set_id>`) with the database(s) it describes — see *Database association* (omit `databases` on temporary `<context_set_id>_draft` uploads). | A long-running operation (`name`). |
| `get_context_set(projectId, location, contextSetId)` | Read a context set. | `{"payload": "<ContextSet JSON string>", "description", "displayName", "databases": [...]}`. When called on a non-existent or deleted `contextSetId` (e.g., probing existence during `init` or verifying deletion), the server returns plain text `"Resource was not found."` in `content[0].text` with `isError: true` rather than a JSON object — treat this response as `NOT_FOUND` (and when reporting `NOT_FOUND` to the user, explicitly state that `<contextSetId>` does not exist in `<location>`; do not probe other locations). |
| `delete_context_set(projectId, location, contextSetId)` | Delete a context set. | A long-running operation (`name`). |
| `get_operation(projectId, location, operationId)` | Poll a long-running operation. | `{"done": bool, ...}` plus `error` on failure. |

## Database association (`databases`)

Every `upload_context_set` in this workflow **must** carry `databases` — the database the context set is for — so QueryData and the console can tie the context set to its source. `databases` is a list of structured objects:

```json
{"databaseType": "<SPANNER|CLOUD_SQL|ALLOYDB|FIRESTORE|BIGTABLE|BIGQUERY>", "projectId": "…", "location": "…", "clusterId": "…", "instanceId": "…", "databaseId": "…", "datasetId": "…"}
```

Keys are camelCase (`databaseType`, `projectId`, `location`, `clusterId`, `instanceId`, `databaseId`, `datasetId`), as in the server's tool schema; `get_context_set` returns `databases` in the same shape, so a returned list can be passed back to `upload_context_set` unchanged.

**Derive it at upload time — never record it.** Take the **Source Name** under `## Active Database` in `experiment_state.md` (standalone: the chosen source), read that `kind: source` block from `.context-engineering/tools.yaml`, and map it with the table below (omit fields that do not apply). `tools.yaml` stays the single place connection details live; `experiment_state.md` only names the source.

| `tools.yaml` source `type` | `databaseType` | `projectId` | `location` | `clusterId` | `instanceId` | `databaseId` | `datasetId` |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| `alloydb-postgres` | `ALLOYDB` | `project` | `region` | `cluster` | `instance` | `database` | — |
| `cloud-sql-postgres`, `cloud-sql-mysql` | `CLOUD_SQL` | `project` | `region` | — | `instance` | `database` | — |
| `spanner` (GoogleSQL or PostgreSQL dialect) | `SPANNER` | `project` | — | — | `instance` | `database` | — |
| `bigtable` | `BIGTABLE` | `project` | — | — | `instance` | — | — |
| `firestore` | `FIRESTORE` | `project` | — | — | — | `database` (e.g. `my-firestore-db`) | — |
| `bigquery` | `BIGQUERY` | `project` | — | — | — | — | `allowedDatasets[0]` (if `project.dataset`, take the segment after `.`) |
| `custom` | *(no `databaseType` exists for `custom`)* — **omit the `databases` argument** for this source; tell the user once that the context set will not be linked to a database. | | | | | | |

Rules:
*   **Pass it on primary context sets (`<context_set_id>`), omit it on temporary `<context_set_id>_draft` working copies** — fresh-case iteration uploads (where `<working_copy>` = `<context_set_id>`), the final candidate upload to `<context_set_id>` (or `<Seed Context Set resource>`), bootstrap's optional upload, and evaluate's standalone upload all include `databases` derived as above from the experiment's **Source Name** + `tools.yaml` (standalone bootstrap/evaluate: from the chosen source). For temporary `<context_set_id>_draft` uploads during hill-climbing (or evaluate inside an existing-case experiment), **omit `databases`** so the temporary `_draft` context set does not appear in the Google Cloud Console (Database Studio) Object Explorer UI during the run or if a session is interrupted before `Finalize`. Evalbench and `QueryData` reference `<context_set_id>_draft` directly by its explicit resource name and do not require `databases` on the draft.
*   **A context set that already existed keeps its association.** The server semantics are: `databases` **omitted** on an update → the existing list is preserved; `databases` **provided** → the whole list is **replaced**. There is no append call — appending means *read the current list, add to it, send the full list*. So, for an existing set:
    *   During the run nothing is written to `<context_set_id>` at all (iterations go to `<id>_draft` **without** `databases`).
    *   At the final replacement (existing-case Finalize, after the user's yes), **never send only the experiment's database**. Call `get_context_set(<context_set_id>)` to read the existing set's current `databases` list and send that list **plus** the derived database (appended, de-duplicated) so nothing already associated is dropped.
    *   The existing set's association is never otherwise edited — no re-asserting, no pruning, no reordering.
*   Never invent values: every field comes from `tools.yaml`; if a required field for the type is missing there, stop and route to `context-engineering-init`.

## Resource naming

A context set resource name has the shape

```
projects/<project_id>/locations/<location>/<collection>/<context_set_id>
```

where `<collection>` is the service's collection segment — **`contextSets` today, expected to become `entryGroups`**. The skills never depend on that segment:

*   **Parsing (always by position, never by validating the collection):** `projectId` = the segment after `projects`, `location` = the segment after `locations`, `contextSetId` = the **last** segment. Accept any collection segment; if the name does not have the `projects/…/locations/…/<collection>/<id>` structure at all, ask the user to re-check it rather than guessing.
*   **Calling tools:** every tool takes the three parsed parts (`projectId`, `location`, `contextSetId`) — never the full string — so the collection segment is irrelevant to tool calls.
*   **Recording names in `experiment_state.md`:** when the user supplied a resource name, record it **verbatim** as the resource it refers to (`Seed Context Set resource`, and `Final Context Set resource` when improving in place). Derive the `Draft Context Set resource` from it by replacing only the last segment with `<context_set_id>_draft`, keeping the user's collection segment. Only when *no* name was supplied (fresh experiment) construct `Final Context Set resource` / `Draft Context Set resource` with the current default collection `contextSets`. If a tool response carries a resource `name`, prefer that string verbatim over a constructed one.
*   **Passing names to Evalbench:** `generate_evalbench_configs(context_set_id=…)` passes the string straight through to Evalbench/QueryData; give it the recorded resource string unchanged.

> [!IMPORTANT]
> **This section is the only definition of the resource-name shape.** Peer skills (`init`, `bootstrap`, `evaluate`, `hillclimb`) and the examples in `context-engineering-hillclimb/references/layout.md` refer to it as *the Resource naming rule* and must not spell out a different path. When the service switches collection, change the default collection word above and the `layout.md` examples; nothing else should need to change.

*   `<context_set_id>` is user-chosen. `context-engineering-init` asks for it once (default: the experiment name) and records it in `experiment_state.md`; peers read it from there.
*   **Working copy — decided by whether `<context_set_id>` already exists when init probes it**, and recorded as the `Draft Context Set resource` bullet:
    *   **Fresh** (did not exist): there is **no `_draft`**. Hill-climbing uploads every iteration straight to `<context_set_id>`, re-uploads the best iteration to the same name at the end, and runs the holdout test on it. Nothing is deleted. `Draft Context Set resource: (none — new context set; iterations upload to the final name)`.
    *   **Existing** (already there): hill-climbing uploads every iteration to `<context_set_id>_draft` and **never writes to `<context_set_id>` during the run**. At the end the best iteration is placed in the draft, the holdout test runs on the draft, and the user is asked — always, regardless of `Auto-approve uploads`, and only if the candidate beats `v0` — whether to replace the existing set. The draft is deleted afterwards either way. `Draft Context Set resource: …/<context_set_id>_draft`.

## Improving a context set that already exists on the Context Set server

When the user hands over an existing resource name ("improve / fix `projects/…/<collection>/<id>`"), `context-engineering-init` parses it (rule above), confirms it exists, records it **verbatim** as `Seed Context Set resource` (its project and location are then carried by that string — `workspace_state.md` is not edited, and a mismatch with the workspace defaults is only mentioned in the summary), and asks **one** question — should the improved version replace it (**same name**, the default) or be published under a **new name**?

*   **Same name** → `Context set id` = parsed `<id>`, `Final Context Set resource` = the supplied string. Because the name exists, the *existing* working-copy rule applies automatically: iterations run on `<id>_draft`, the original is untouched until the end-of-run HITL, and the original payload is kept locally as `v0/context_set_v0.json`.
*   **New name** → `Context set id` = the new name; it does not exist, so the *fresh* rule applies and the seed is never written to.

In both cases hillclimb seeds `v0` from the existing resource via `get_context_set` (not bootstrap). No extra bookkeeping (`Publish mode` or similar) is needed — the `Seed Context Set resource`, `Final Context Set resource` and `Draft Context Set resource` bullets fully determine the behaviour.

## Context Set Location resolution

Context Set location (the location where Context Sets are stored) is resolved **once per workspace**, by `context-engineering-init` when it writes `workspace_state.md`: it calls `list_context_set_locations(projectId)`, lets the user pick (or confirms a named location is in the list), and records the choice there under `## Context Set coordinates`. When the user supplied an existing resource name, the location parsed from it is used for that experiment and only confirmed against the list — not re-asked. Peers never call `list_context_set_locations` again: for tool calls they parse the location from the experiment's resource names (below). Do not assume a default location or copy the database region.

## Inputs & resolution rules (`workspace_state.md` vs `experiment_state.md`)

Two files, two jobs. `.context-engineering/workspace_state.md` holds **what the user entered once for the workspace** — Context Set `Project`, Context Set `Location` (under `## Context Set coordinates`), `Default DB source`, `Enrichment sources`, `Auto-approve uploads` (format and example in `context-engineering-hillclimb/references/layout.md`). Each `experiments/<name>/hillclimb/experiment_state.md` holds **the record of one run** — `Context set id`, `Final Context Set resource`, `Draft Context Set resource`, `Seed Context Set resource`, datasets, `## Active Database`, iterations, verdict. Resolution:

1.  **Context-set identity never comes from `workspace_state.md` after init.** Every tool call parses `projectId` / `location` / `contextSetId` from `Final Context Set resource` / `Draft Context Set resource` / `Seed Context Set resource` in `experiment_state.md` (Resource naming rule). Init consumes `workspace_state.md`'s `Project`/`Location` exactly once, to construct `Final Context Set resource`. Consequence: editing `workspace_state.md` later cannot retarget a running experiment, and improving a resource that lives in another project needs no override.
2.  **`Auto-approve uploads`** — effective value = `Auto-approve uploads (this experiment)` in `experiment_state.md` if present → else `workspace_state.md` → else `false`. Hillclimb re-reads it on every entry.
3.  **`Enrichment sources`** — `Enrichment sources (this experiment)` in `experiment_state.md` if present → else `workspace_state.md`. Read by dataset-generation (realistic questions, terminology) and by bootstrap when hillclimb seeds `v0` (business terms, join rules). User-facing wording never says "bootstrap" — say "the evaluation questions and the initial context set".
4.  **`Default DB source`** — `## Active Database` in `experiment_state.md` is authoritative once written; `workspace_state.md` only pre-fills init.
5.  **Only `context-engineering-init` writes `workspace_state.md`** (creation, "change my defaults", a new Default DB source). Every other skill is read-only on it; a user asking mid-run to change a default is routed to init.
6.  **New experiment while the file exists**: init shows the recorded inputs verbatim and asks once — keep / change for this experiment only (→ `(this experiment)` bullets in `experiment_state.md`) / change the defaults (→ file updated with a `## History` line). It never silently reuses them without showing them.

> [!IMPORTANT]
> This section is the only definition of the precedence between the two files. Peer skills refer to it as *Inputs & resolution rules* and must not restate a different order.

## Writing a context set from disk

`upload_context_set` accepts the ContextSet only as an inline JSON string in `contextPayload`. Even for ad-hoc or minimal test uploads, **the agent must run the local `validate_context_set` tool before calling `upload_context_set`**. To upload a file:

1.  Run `validate_context_set` (local plugin tool) on the file. Do not upload a file that fails validation.
2.  Read the file with ordinary file tooling.
3.  Call `upload_context_set` with `contextPayload` set to the **exact, complete** file contents. Do not summarise, reformat, truncate, or "fix" the JSON on the way through; the payload must round-trip byte-for-byte in meaning.
4.  Follow the poll gate below.

## Long-running operations — the poll gate

`upload_context_set` and `delete_context_set` are **asynchronous**: the tool returns as soon as the request is accepted, not when the work is done. After either call:

1.  Take `name` from the response. It has the form `projects/<project_id>/locations/<location>/operations/<operation_id>`; the last path segment is the `operationId`.
2.  Call `get_operation(projectId=…, location=…, operationId=…)` with those three parts.
3.  If `done` is not `true`, wait **at least 5 seconds** and call again (the server asks for ≥5 s between polls). Stop after 5 minutes total.
4.  Log every poll response so the user can see progress.
5.  **`done: true` means the operation is complete.** Continue with the next step. No additional verification call is needed.
6.  `done: true` together with an `error` field means the operation failed. Surface the error verbatim and stop.
7.  If the 5-minute ceiling is reached, surface the operation name and stop.

**Never act on a context set whose upload operation has not yet reported `done: true`.** In particular, `evaluate` must not generate Evalbench configs or launch an evaluation until the upload it depends on is done; otherwise the evaluation runs against a missing or stale context set and its score is meaningless.

## Reading a context set to disk

`get_context_set` returns the ContextSet as a JSON string in `payload`. Parse it and write it to the target path with ordinary file tooling; the tool does not write files.

## Overwrite hazard

`upload_context_set` is an upsert: uploading to a `<context_set_id>` that already exists **silently replaces its contents**, and the previous contents cannot be recovered from the server. The skills handle this structurally rather than with a one-time acknowledgement:

1.  `context-engineering-init` probes the bare `<context_set_id>`. If it exists, it **warns the user up front** (iterations will go to `_draft`; the existing set is untouched until the end; one `delete_context_set` on the draft will follow) and offers a different name.
2.  During the run, an existing `<context_set_id>` is **never written**.
3.  At the end, the holdout test runs on the candidate **before** anything is replaced, and the replacement is a **mandatory HITL** — previous vs new results side by side — asked only if the candidate beats `v0`, and regardless of `Auto-approve uploads`. The previous contents are preserved locally as `v0/context_set_v0.json` and can be re-uploaded on request.

A fresh `<context_set_id>` (NOT_FOUND at init) needs none of this: it is created by the first iteration upload and never contained anything else.

## Idempotent delete

A `delete_context_set` that fails with NOT_FOUND is treated as success. This matters when resuming an interrupted hill-climb run, where a draft may already have been removed.
