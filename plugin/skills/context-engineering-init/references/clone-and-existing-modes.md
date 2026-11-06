# Reviewing Existing Workspace Inputs, Clone Mode & Existing-Context-Set Mode

> **Parent Skill Reference**: This reference is used during the **Initialise the experiment `experiment_state.md`** workflow defined in [`context-engineering-init`](../SKILL.md) whenever `.context-engineering/workspace_state.md` already existed from an earlier setup, when cloning a finished experiment, or when improving an existing published Context Set.

## Review the workspace inputs (when `workspace_state.md` already existed from an earlier setup — skip if you just created `workspace_state.md` in this turn)

Print the recorded inputs verbatim and ask **one** question:

> *"I'll use the inputs recorded in `.context-engineering/workspace_state.md` for this experiment:*
> *– Context Set project `<project>`, Context Set location `<location>`*
> *– Default DB source `<source>` (`tools.yaml`)*
> *– Enrichment sources: `<list or none>`*
> *– Uploading draft iterations: `<automatically | pause for my approval before each>`*
> *Keep these, change some for this experiment only, or change the defaults?"*

- **Keep** → continue with step 1 in [`SKILL.md`](../SKILL.md); `experiment_state.md` gets no copy of these values.
- **Change for this experiment only** → the experiment deviates without touching the file. DB source → recorded in `## Active Database` as usual (step 5). Enrichment sources → `Enrichment sources (this experiment): [...]` in `## Metadata`. Upload approval → `Auto-approve uploads (this experiment): <true|false>` (the same neutral draft-iterations question as in `Record the workspace inputs`, answered for this run). Context Set Project/Location cannot be overridden per experiment — they are workspace defaults; if the user wants another Context Set project or location, that is a default change.
- **Change the defaults** → update `workspace_state.md` (with a `## History` line), then continue.

---

## Clone mode (follow-up to a finished experiment)

Triggered when the user names a source experiment (e.g. *"cloned from `<source>` for context fixes / dataset expansion"*, usually via the hand-off card printed by `context-engineering-workflow`). Before step 1 in [`SKILL.md`](../SKILL.md):
- Verify `.context-engineering/experiments/<source>/hillclimb/experiment_state.md` exists and has `## Final:`; read its `Final Context Set resource`, `## Active Database`, dataset bullets, verdict, and `.context-engineering/experiments/<source>/hillclimb/final_evaluation_report.md`.
- **Copy `golden.json` only**: `<source>/dataset/golden.json` → `.context-engineering/experiments/<experiment_name>/dataset/golden.json`. Never copy `splits/`, plans or audit reports — the new experiment must first incorporate the generalizability findings/recommendations from `<source>/hillclimb/final_evaluation_report.md` into the copied `golden.json` (adding the recommended query/phrasing/value variations) and **only after `golden.json` is updated** run `split_dataset` so it gets an uncontaminated `splits/holdout.json` while preserving the base domain distribution.
- Record both `- Source evaluation report: ./.context-engineering/experiments/<source>/hillclimb/final_evaluation_report.md` and `- Golden dataset: ./.context-engineering/experiments/<experiment_name>/dataset/golden.json (cloned; expand with recommendations from source evaluation report before split)` under `## Metadata` in `experiment_state.md` so `context-engineering-dataset-generation` reads the previous generalizability report, applies its recommended variations to `golden.json`, and splits only after expansion is complete.
- Pre-fill: `Seed Context Set resource` = source's published resource (`Final Context Set resource`, if it was published; otherwise the source's best local file); `## Active Database` = source's (same `tools.yaml` source — confirm it still exists in `tools.yaml`). Project/Location come from `workspace_state.md` like any other experiment. Record only the `Golden dataset` bullet — the split bullets are written by the dataset skill after `split_dataset`. Skip the DB connection questions.
- `Context set id` still defaults to the **new** experiment name (step 2), so the clone works in its own context set during the loop and the source's published set is never touched during iterations (at Finalize, if the clone improves over `v0`, hillclimb asks whether to also upload the improved contents back to `Seed Context Set resource` or keep the two context sets separate). When suggesting or defaulting a cloned experiment name from `<source>`, strip any trailing `-v<N>` suffix and pick the next unused `-v<N>` in `.context-engineering/experiments/` (e.g. `my-exp` → `my-exp-v2`, and a third experiment cloned from either `my-exp` or `my-exp-v2` → `my-exp-v3`, never `my-exp-v2-v2`).

---

## Existing-context-set mode (the user wants to improve a context set that is already published)

Triggered when the user supplies a resource name — *"improve / fix `projects/<p>/locations/<l>/<collection>/<id>`"*. Before step 1 in [`SKILL.md`](../SKILL.md):
- **Parse it per the Resource naming rule** in `context-engineering-workflow` ([`ctxset-mcp-protocol.md`](../../context-engineering-workflow/references/ctxset-mcp-protocol.md)): `projectId` = segment after `projects`, `location` = segment after `locations`, `contextSetId` = last segment. **Do not validate or depend on the collection segment** (`contextSets` today, `entryGroups` later — both must work unchanged). If the string lacks that structure, ask the user to re-check it; never guess.
- Confirm it exists: `get_context_set(projectId, location, contextSetId)`. NOT_FOUND (including when the remote server returns plain text `"Resource was not found."` in `content[0].text` with `isError: true`) → tell the user explicitly that context set `<contextSetId>` does not exist in location `<location>` (do **not** probe other locations and do **not** create anything) and ask for a corrected resource name or location. Keep the response's `description` for the summary.
- Record `Seed Context Set resource: <the supplied string, verbatim>`. The resource's own project and location are authoritative for this experiment (identity is always parsed from the resource names in `experiment_state.md`); if they differ from `workspace_state.md`, say so in the summary — do **not** edit `workspace_state.md`.
- Ask **one** question: *"Should the improved version replace `<supplied name>` (same name), or be published under a new name?"* Default for this flow: **same name**. Same name → `Context set id` = parsed `<context_set_id>` and `Final Context Set resource` = the supplied string verbatim (step 3 will then find it exists and set up the draft strategy). New name → continue with step 2 as usual.
- `v0` comes from the seed, not from bootstrap (hillclimb downloads it).

---

## Existing Resource Collision Warning (Step 3 `Exists` Branch)

When probing `get_context_set(projectId=<project>, location=<location>, contextSetId=<context_set_id>)` in step 3 of `Initialise the experiment experiment_state.md` and the Context Set **already exists**:
- Record `Draft Context Set resource: <Final Context Set resource with its last segment replaced by <context_set_id>_draft>` (same collection segment).
- Tell the user — this is the only warning they get before the end:
  *"`<Final Context Set resource>` already exists. I will not touch it during the run: iterations go to `<Draft Context Set resource>`. At the end I'll run the holdout test on the draft, show you the current vs new results, and **ask** before replacing `<Final Context Set resource>` — and only if the new one is better. A replacement changes only its context payload; its existing database association is kept. Either way the draft is deleted afterwards (expect one `delete_context_set` call)."*
- If the user did **not** supply this resource as their seed (they just reused a name), also offer to pick a different `Context set id` instead; if they choose another name, re-probe.

---

## Engine-Specific `## Active Database` Scope Fields (Step 5 Details)

When recording `## Active Database` in `experiment_state.md`:
- Verify the source block in `.context-engineering/tools.yaml` has the required fields for its `databaseType` mapping in `upload_context_set` (AlloyDB: `project`/`region`/`cluster`/`instance`/`database`; Cloud SQL: `project`/`region`/`instance`/`database`; Spanner: `project`/`instance`/`database`; Bigtable: `project`/`instance`; Firestore: `project`/`database`; BigQuery / custom: none — no database association is sent for these) and ask the user to complete `tools.yaml` if one is missing.
- **Spanner GoogleSQL**: call `<source>-list-graphs` and record the property graph ids as `- **Graph Ids**: [...]` (`[]` if none) — `generate_evalbench_configs` reads this bullet.
- **BigQuery**: record the tables in scope as `- **Table Ids**: [...]` (from `<source>-list-schemas`; at least one — the QueryData API requires explicit table references and `tools.yaml` has no place for them) — `generate_evalbench_configs` reads this bullet too.
- **Cloud Bigtable & Firestore**: optionally record the target tables/logical views or collections in scope as `- **Table Ids**: [...]` so `generate_evalbench_configs` populates `bigtable_reference.database_reference.table_ids` or `firestore_reference.database_reference.collection_ids` and scopes QueryData schema discovery.
