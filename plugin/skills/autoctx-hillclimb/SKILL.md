---
name: skill-autoctx-hillclimb
description: Iteratively improve a ContextSet by running evaluation, analyzing failures, mutating, and re-evaluating. Owns an internal, resumable workspace; composes bootstrap, upload, and evaluate.
---

# Auto Context Hill-Climbing

## Goals

Progressively raise a ContextSet's eval score by alternating evaluate → analyze → mutate → re-upload, until convergence or the user halts. Resumable across sessions.

## Prerequisites

- A `tools.yaml` with the target DB configured (refer the user to `skill-autoctx-init` if missing).
- A golden dataset file in the simplified user-facing format (see `skill-autoctx-evaluate` for the schema).
- Application Default Credentials configured for the Context Store (`gcloud auth application-default login`).
- A starting context — one of three forms:
  1. **None** → invoke `skill-autoctx-bootstrap` to generate one.
  2. **Local file** → upload via `upload_context_set` before iterating.
  3. **Existing resource name** → iterate directly.

## Guidances

### Workspace (internal)

Hillclimb owns its own workspace, default path `./autoctx-experiment/<experiment_name>/`. The folder layout below is a **reference convention**, not a contract — keep iteration data scoped to the workspace so the convention can be swapped later (eg. for git-based versioning) without touching this skill's contract.

```
autoctx-experiment/<experiment_name>/
├── state.md
├── v1/
│   ├── context.json              # local copy of the v1 ContextSet
│   ├── gap_analysis.md
│   ├── eval_configs/             # YAMLs generated for this iteration's eval
│   └── eval_reports/<job_id>/    # evaluate output
├── v2/...
```

`state.md` (the only file the agent reads to resume) tracks experiment metadata and per-iteration outcomes. Markdown format — easy to `cat` and inspect; agent-native to read and append:

```markdown
# Experiment: orders_demo

- **Target DB**: my-postgres-instance (source `pg_main` in tools.yaml)
- **Golden dataset**: /abs/path/to/golden.json
- **Base context**: <local path | resource name>
- **Current iteration**: v2

## Iterations

- **v1** — context_set_id: `projects/.../contextSets/orders_demo_autoctx@v1`, eval_job_id: `...`, score: 0.62
- **v2** — context_set_id: `projects/.../contextSets/orders_demo_autoctx@v2`, eval_job_id: `...`, score: 0.71
```

### Entry flow

1. **Locate the workspace.** Ask the user for `experiment_name`. Compute workspace path. If the path already has a `state.md`, this is a resume; otherwise a fresh start.
2. **Resume branch.** If `state.md` exists:
   - Read it. Report back: `found experiment <X> at <vN> (score Y); continue to v(N+1)?`
   - On yes, skip to "Per-iteration loop" with `N := current+1`.
   - On no, ask whether to abandon, rename, or pick a different `experiment_name`. Never overwrite an existing workspace silently.
3. **Fresh-start branch.** If `state.md` does not exist:
   - Create the workspace directory.
   - Ask the user for the base context (the three forms in Prerequisites). For form 1, invoke `skill-autoctx-bootstrap` and use the resulting file. For form 2, accept the local path. In both cases, follow with an `upload_context_set` call:
     - `csg_id`: `<experiment_name>`
     - `cs_id`: `autoctx`
     - `version`: `v0` (the pre-iteration baseline)
   - For form 3, use the supplied resource name as v0; download it via `download_context_set` to seed `v1/context.json` for local mutation.
   - Ask the user for the golden dataset absolute path and the Toolbox source name.
   - Write the initial `state.md` with `Base context`, `Target DB`, `Golden dataset`, and `Current iteration: v0`. Start the loop with `N := 1`.

### Per-iteration loop (vN)

Each iteration is sequential — one analyzer, one mutator. No parallel subagents.

1. **Prepare iteration directory.** Create `vN/`. Copy the previous version's context.json to `vN/context.json` (for v1, this is the v0 baseline pulled fresh from the Context Store via `download_context_set`).
2. **Evaluate.** Invoke `skill-autoctx-evaluate` with:
   - The most recent resource name (v(N-1) for N>1, or the v0 baseline for N=1).
   - Golden dataset path from `state.md`.
   - `tools.yaml` + source name from `state.md`.
   - `output_dir`: the absolute path of `<workspace>/vN/` (configs land in `vN/eval_configs/`, reports in `vN/eval_reports/`).
   When it returns, capture `job_id` and overall score.
3. **Analyze failures.** Read `vN/eval_reports/<job_id>/scores.csv` and `summary.csv` directly with the `Read` tool. Cluster failures by category (missing template, wrong join, ordering miss, vocabulary gap, syntactically broken golden SQL, etc.). Write `vN/gap_analysis.md` with a summary section followed by per-failure entries (query, expected SQL, actual SQL, root cause, proposed mutation type).
4. **Human-in-the-loop.** Report the score and a brief summary of dominant failure categories. Ask the user whether to proceed to mutation, halt, or edit `gap_analysis.md` first. Wait for explicit confirmation.
5. **Mutate.** Plan mutations from `gap_analysis.md`. Prefer fewer, more general items (a facet over many specific templates). For any new template / facet / value search, invoke `skill-context-generation-guide` to produce parameterized JSON. Validate before applying:
   - Templates: run their SQL via `<source>-execute-sql` with dummy parameter values.
   - All types: cross-check column/table references via `<source>-list-schemas`.
   Apply via `mutate_context_set` against `vN/context.json`.
6. **Upload as new version.** Call `upload_context_set(vN/context.json, csg_id=<experiment_name>, cs_id="autoctx", version="vN")`. Record the returned resource name.
7. **Update `state.md`.** Append the iteration entry (resource name, job_id, score). Bump `Current iteration` to `vN`.
8. **Decide whether to continue.** Compare score to v(N-1). Report delta. Ask the user whether to run v(N+1), pause (workspace is fully resumable), or stop. Default behavior on user "continue" is to loop back to step 1 with `N := N+1`.

### Failure handling

- If `upload_context_set` returns 409, the version already exists (resume bug or workspace corruption). Stop, show the user, and ask for direction — never silently bump.
- If evaluate fails to run, stop and surface the error. Do not roll forward state.
- If mutation produces zero changes (eg. all failures are golden-dataset bugs), record this in `state.md` and ask the user whether to halt or fix the golden dataset and retry.

## Rules

- **The workspace is internal.** Do not surface folder paths as part of the user contract — only `context_set_id`, score, and iteration number. The user can `cat state.md` if they want detail.
- **Never overwrite an existing version.** A 409 from upload is a hard stop, not a retry signal.
- **Always confirm with the user between iterations.** This is not a fully autonomous loop; hill-climbing requires per-step human approval to mutate.
- **Do not write a global `state.md` outside the workspace.** The old shared `autoctx/state.md` is gone. Other skills know nothing about hillclimb's state.
- **Only `templates` and `facets` are emitted as mutations**, plus `value_search` when a vocabulary gap is explicit in the failure data. Do not invent other context types.
- **Bootstrap and evaluate are composed, not duplicated.** Don't reimplement schema fetching or EvalBench config generation — invoke the sibling skills.

## Tools

- **`skill-autoctx-bootstrap`** — invoked when there is no base context.
- **`skill-autoctx-evaluate`** — invoked once per iteration to score the current version.
- **`skill-context-generation-guide`** — invoked when new context items need to be authored.
- **`upload_context_set`** (MCP) — pushes each iteration's mutated context as the next version. Returns the resource name.
- **`download_context_set`** (MCP) — seeds `v1/context.json` when the user starts from a pre-existing resource name.
- **`mutate_context_set`** (MCP) — applies the planned mutations to the local context file.
- **`<source>-execute-sql`, `<source>-list-schemas`** (Toolbox MCP) — validate generated templates and column references.
- **Read / Write / Edit** — to read `scores.csv` and `summary.csv` directly, write `gap_analysis.md`, append to `state.md`.
