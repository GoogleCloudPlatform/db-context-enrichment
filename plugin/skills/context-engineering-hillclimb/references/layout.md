# Hill-Climbing Workspace Layout

The hill-climbing skill maintains an internal workspace to track iterations, evaluation reports, and mutation history. Everything for one run lives under a single root:

- `.context-engineering/tools.yaml` — the **single shared** Toolbox configuration for the workspace (user-owned; may hold several DB sources). The Toolbox MCP server reads it at startup only, so any edit — by a skill or by the user — needs a `toolbox` server restart.
- `.context-engineering/workspace_state.md` — the **workspace inputs**: what the user entered once (Context Set `Project` / `Location`, `Default DB source`, `Enrichment sources`, `Auto-approve uploads`). Written only by `context-engineering-init`; read by everything else. Format below.
- `<experiment_root>` = `.context-engineering/experiments/<experiment_name>/` — **per experiment**, with two siblings: `dataset/` (owned by `context-engineering-dataset-generation`) and **`hillclimb/`** (owned by the hill-climb loop).
- `<hillclimb_root>` = `<experiment_root>/hillclimb/` — `experiment_state.md` (the record of the run; it never duplicates the workspace inputs), the iteration directories `v<N>/`, `holdout_eval/` and `final_evaluation_report.md`. **Unless stated otherwise, relative paths below are relative to `<hillclimb_root>`.**

## Directory structure

```
.context-engineering/
├── tools.yaml                             # shared Toolbox DB connections (context-engineering-init / user)
├── workspace_state.md                     # workspace inputs the user entered once (context-engineering-init)
└── experiments/
    └── <experiment_name>/                 # <experiment_root> — one per experiment
        ├── dataset/                       # context-engineering-dataset-generation (deliverables + working files)
        │   ├── golden.json                # full golden dataset
        │   ├── splits/
        │   │   ├── hillclimb.json         # optimization split — the only dataset the loop evaluates on
        │   │   └── holdout.json           # held out until the loop converges; never read by the loop
        │   ├── evalset_environment_inputs.md  # domain map, artifact registry, seed pairs
        │   ├── evalset_gen_plan.md        # user-approved generation plan
        │   ├── temp_golden.json           # interim dataset during generation/expansion
        │   ├── evalset_report_pair_level.md     # audit report 1
        │   └── evalset_report_dataset_level.md  # audit report 2
        └── hillclimb/                     # <hillclimb_root> — everything the hill-climb run produces
            ├── experiment_state.md        # written by init; context set identity + which tools.yaml source is used + per-iteration scores
            ├── v<N>/                      # one directory per iteration (v0 = base, v1+ = mutations)
            │   ├── context_set_v<N>.json  # ContextSet snapshot at this version
            │   ├── analysis_v<N>.md       # findings + reasoning + mutations applied
            │   └── eval/                  # output_dir for context-engineering-evaluate
            │       ├── eval_configs/      # generated Evalbench YAMLs + converted dataset
            │       │   ├── db_config.yaml
            │       │   ├── model_config.yaml
            │       │   ├── run_config.yaml
            │       │   ├── llmrater_config.yaml
            │       │   └── golden_queries.json
            │       └── eval_reports/<job_id>/
            │           ├── scores.csv
            │           └── summary.csv
            ├── holdout_eval/              # output_dir for the single holdout evaluation (after convergence, before any replacement)
            └── final_evaluation_report.md # generalizability report (Holdout Evaluation phase)
```

An experiment is **self-contained and, once `## Final:` is written, frozen**. Follow-up work happens in a new experiment that `context-engineering-init` **clones** from the finished one: it copies **only `dataset/golden.json`** — never `splits/`, plans or reports — and the new experiment produces its own split with `split_dataset`. The clone points at the **same `tools.yaml` source** (carried over in `## Active Database`; the shared `tools.yaml` is never copied). The finished experiment's result (its published context set, or its best local file if it was not published) becomes the clone's `Seed Context Set resource` and is never overwritten. Nothing else about the source experiment is recorded.

## `workspace_state.md` format

Workspace-level, written only by `context-engineering-init` (first experiment, or on request to change a default). Downstream skills read it; they never write it. Precedence between this file and an experiment's `experiment_state.md` is defined once, under *Inputs & resolution rules* in `context-engineering-workflow`: context-set identity always comes from the resource names in `experiment_state.md`; `Auto-approve uploads` and `Enrichment sources` come from `experiment_state.md` only when it carries an explicit `(this experiment)` override, otherwise from here; `Default DB source` only pre-fills init (the experiment's `## Active Database` is authoritative once written).

```markdown
# Context Engineering Inputs

## Context Set coordinates
- **Project**: my-project
- **Location**: us-central1

## Database
- **Config**: ./.context-engineering/tools.yaml
- **Default DB source**: my-alloydb

## Enrichment sources
- ./docs/design.md
- ./app/models/

## Preferences
- **Auto-approve uploads**: false        # draft iterations: upload automatically (true) or pause for approval before each (false)

## History
- **Created**: 2026-10-12
- **Updated**: 2026-10-14 — Auto-approve uploads changed to false on request
```

`Enrichment sources` may be a single `- (none)`. Nothing per-experiment ever goes here (no context set ids, resource names, `Database` objects, dataset paths, scores), and the hillclimb stopping rules are never recorded anywhere.

## `experiment_state.md` format

`experiment_state.md` is the single source of truth for the experiment. `context-engineering-init` creates it with the first two sections; later phases append to it. It must contain:

- **Metadata** (init) — the experiment root, the context set identity, and the dataset bullets. Identity is carried by resource names only: `Context set id`, `Final Context Set resource` (derived by init from `workspace_state.md`'s `Project`/`Location` using the **Resource naming rule** in `context-engineering-workflow` — the examples below show the current shape, but that rule is the only definition of it), `Draft Context Set resource` (init probes whether the final name already exists: `(none — new context set; iterations upload to the final name)` for a fresh name, or `…/<context_set_id>_draft` when the name already existed — the existing set is then never written during the run and only replaced after the holdout test and an explicit yes), and `Seed Context Set resource` (a user-supplied existing resource recorded **verbatim**, whatever collection segment it uses; `(none — seeded from bootstrap)`; or `(local file: …)`). **No `Project`, `Location`, `Auto-approve uploads` or `Enrichment sources` bullets** — those live in `workspace_state.md`; the only exceptions are the explicit per-run overrides `Auto-approve uploads (this experiment): …` and `Enrichment sources (this experiment): […]` written when the user chose differently for this experiment in init's review step. Stopping rules (tuning target, plateau, iteration cap) are internal constants of the hillclimb skill and are not recorded — only the outcome (`## Converged: <reason>`) is. Dataset paths point inside the experiment: `Golden dataset` (`dataset/golden.json` — the only dataset file a user or a clone can bring in) carries its handling in parentheses — `(split as is)` for a clone after context fixes, `(expand before split)` for a clone after a dataset-expansion verdict or a user-supplied file, `(generated)` once dataset-generation produced it; `Hillclimb dataset` / `Holdout dataset` (`dataset/splits/…`) are written **only** by `context-engineering-dataset-generation` after `split_dataset` — splits are never user-supplied or copied.
- **Active Database** (init; expanded by dataset-generation / hillclimb) — **which `tools.yaml` source this experiment uses**: `**Config**` (always `./.context-engineering/tools.yaml`), `**Source Name**`, `**Type**`, `**Tools**` (the exact tool names declared for that source), `**Graph Ids**` for Spanner GoogleSQL property graphs, `**Table Ids**` for BigQuery (the tables in scope; at least one), and — only when `v0` was downloaded from an existing resource — `**Seed databases**`: the `databases` list `get_context_set` returned, verbatim, or `(not returned)` when the response had no such field. It is used once, at the final replacement of an existing set, to **append** this experiment's database to the existing association (or to leave the association untouched when it could not be read); the existing set's `databases` are never replaced by ours. No connection details or database object are copied here: every `upload_context_set` derives its `databases` argument from **Source Name** + that source's block in `tools.yaml` (see *Database association* in `context-engineering-workflow`). Downstream skills take the source from here rather than guessing from a multi-source `tools.yaml`; `generate_evalbench_configs` reads `**Graph Ids**` / `**Table Ids**` from this file to scope Spanner Graph / BigQuery evaluations.
- **Iteration Log** (hillclimb) — one entry per completed iteration, in order. Each entry records the local file, the score, and the working-copy upload operation name.
- **Generalizability** (holdout phase, written **before** `## Final`) — the candidate evaluated (the working copy), holdout score, verdict, and report path.
- **Final** (hillclimb) — written last by the Finalize step: where the result lives (or "not published"), plus the publish / draft-delete operation names where applicable. Its presence marks the experiment as finished and read-only.

Example:

```markdown
# Hill-Climbing Experiment: my-exp-1

## Metadata
- Workspace: ./.context-engineering/experiments/my-exp-1/
- Context set id: my-exp-1
- Final Context Set resource: projects/my-project/locations/us-central1/contextSets/my-exp-1
- Draft Context Set resource: (none — new context set; iterations upload to the final name)
- Seed Context Set resource: (none — seeded from bootstrap)
- Golden dataset: ./.context-engineering/experiments/my-exp-1/dataset/golden.json (generated)
- Hillclimb dataset: ./.context-engineering/experiments/my-exp-1/dataset/splits/hillclimb.json
- Holdout dataset: ./.context-engineering/experiments/my-exp-1/dataset/splits/holdout.json

## Active Database
- **Config**: ./.context-engineering/tools.yaml
- **Source Name**: my-alloydb
- **Type**: alloydb-postgres
- **Tools**: my-alloydb-list-schemas, my-alloydb-execute-sql
- **Graph Ids**: []

## Iteration Log

### v0 (base)
- Local file: v0/context_set_v0.json
- Upload op: projects/my-project/locations/us-central1/operations/operation-...-a1
- Score: 0.42
- Eval report: v0/eval/eval_reports/<job_id>/
- Notes: baseline generated by context-engineering-bootstrap

### v1
- Local file: v1/context_set_v1.json
- Upload op: projects/my-project/locations/us-central1/operations/operation-...-b1
- Score: 0.58
- Analysis: v1/analysis_v1.md
- Eval report: v1/eval/eval_reports/<job_id>/

### v2
- Local file: v2/context_set_v2.json
- Upload op: projects/my-project/locations/us-central1/operations/operation-...-c1
- Score: 0.55
- Analysis: v2/analysis_v2.md
- Eval report: v2/eval/eval_reports/<job_id>/

## Converged: Plateau reached over 3 consecutive mutations.

## Generalizability
- Candidate: projects/my-project/locations/us-central1/contextSets/my-exp-1 (v1 in the working copy)
- Holdout eval: holdout_eval/eval_reports/<job_id>/
- Holdout score: 0.56 (25 / 45)
- Verdict: PASS
- Report: final_evaluation_report.md

## Final: projects/my-project/locations/us-central1/contextSets/my-exp-1 (from v1, score 0.58)
- Candidate upload op: projects/my-project/locations/us-central1/operations/operation-...-f1
```

The `## Final:` line takes one of three forms — fresh case: `## Final: <Final Context Set resource> (from vK, score S)`; existing case, replaced: `## Final: <Final Context Set resource> (from vK, score S) — replaced previous contents` with the publish and draft-delete operation names; existing case, kept: `## Final: not published — <Final Context Set resource> unchanged; best candidate vK/context_set_vK.json (score S)` (or `… — no improvement over v0; …`) with the draft-delete operation name.

## Markers

`experiment_state.md` carries markers that let a resume distinguish crash, intentional stop, user stop, and an interrupted finalize. "Working copy" below means the bare `<context_set_id>` when `Draft Context Set resource` is `(none …)` (fresh case) and `<context_set_id>_draft` otherwise (existing case).

- `## In-Progress: vN` — written at the start of iteration N (per-iteration step 1); removed when the final `### vN` entry lands (per-iteration step 6). A leftover marker means the prior run crashed mid-iteration — possibly after the working copy was already overwritten with the half-finished `vN`.
- `## Converged: <reason>` — appended when a stopping condition fires. `<reason>` is one of `Tuning target <t> reached.`, `Plateau reached over <k> consecutive mutations.`, `Maximum iterations (<n>) reached.`
- `## User Stop` — appended when the user explicitly asks the loop to stop.
- `## Finalizing: vK` — written when the candidate `vK` is chosen, before it is (re-)uploaded to the working copy. Replaced by `## Final: …` at the very end of Finalize. A leftover marker means finalize was interrupted somewhere between candidate upload, holdout test and publication decision.
- `## Generalizability` — written by the Holdout Evaluation phase **before** `## Final:`; it records the verdict for the candidate in the working copy.
- `## Final: …` — written last. **Its presence means the run is complete** and the experiment is read-only.

Completed iterations are preserved in every case — never deleted.

## Resume rules

On skill invocation with an existing workspace:

1. Read `experiment_state.md`, and `.context-engineering/workspace_state.md` for the effective `Auto-approve uploads` (a `(this experiment)` override in `experiment_state.md` wins; otherwise the workspace value; otherwise `false`).
2. Determine the last completed iteration `N`.
3. **Check for `## In-Progress: vM`.** If present, the prior run crashed mid-iteration `M`:
   1. Delete the partial `vM/` directory (its files are not trustworthy) and remove the marker.
   2. The working copy may hold a half-finished `vM`: re-upload `v(M-1)/context_set_v(M-1).json` to the working copy (read the file, pass its exact contents as `contextPayload`) and poll `get_operation` until `done: true`.
   3. Re-run iteration `M` from step 1, seeding from `v(M-1)/context_set_v(M-1).json` on disk.
4. **Check for `## Finalizing: vK`** (and no `## Final:`). Finalize was interrupted. Re-upload `vK/context_set_vK.json` to the working copy unconditionally (do not try to infer what the server holds), then: if `## Generalizability` is missing, run the Holdout Evaluation phase; then run Finalize step 4 — in the existing case this means **asking the replacement question again** (never assume an earlier answer), then deleting the draft (NOT_FOUND = success) — and write `## Final:`.
5. If `## Final:` is present, the experiment is **finished and read-only**: do not add iterations, uploads, or dataset changes. Report the final line and verdict; for non-PASS verdicts re-print the *Next experiment hand-off* card from `context-engineering-workflow` (clone scope per the verdict), then stop. If the user wants to improve further, route to `context-engineering-init` in clone mode.
6. If `## Converged` is present without `## Finalizing`, run Finalize from step 1 — do not start another iteration.
7. If `## User Stop` is present without `## Final:`, ask once whether to continue the loop or finalize now; do not finalize on your own.
8. Otherwise, start iteration `N+1`. Check the stopping conditions first — a resume after the iteration cap must not add an iteration.

## Final output

The `## Final:` line — either the resource the best-scoring iteration now lives under, or "not published" with the existing resource left unchanged — together with the candidate's score, local file path, and the generalizability verdict. No `_draft` resource should remain on the server when a run is complete.
