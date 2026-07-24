---
name: context-engineering-hillclimb
description: Autonomously improve a ContextSet by iterating evaluate → analyze → mutate → re-upload until convergence, given a golden dataset and (optionally) a base context. The user supplies inputs once; no per-iteration approval needed.
---

> **Load [`context-engineering-workflow`](../context-engineering-workflow/SKILL.md) first** for shared terminology, lifecycle overview, and safety protocol.

# Skill: Automated Hill-Climbing

## Goal
Given a golden dataset and (optionally) a base context, autonomously produce a high-quality ContextSet by iterating evaluate → analyze → mutate → re-upload until convergence. The user supplies inputs once and receives the final high-scoring ContextSet; no per-iteration approval is required.

## Prerequisites
- A working DB connection — Toolbox MCP tools (`<source>-list-schemas`, `<source>-execute-sql`) must be visible to the agent throughout the run. If missing or unreachable at any point, stop and route through `context-engineering-init`; do not work around it (no bash `uvx toolbox-server invoke` fallback).
- A golden evaluation dataset (JSON, simplified format: `{id, database, nlq, golden_sql}` — see `context-engineering-evaluate`).
- ADC configured and the Gemini Data Analytics + Dataplex APIs enabled on the project (see `context-engineering-init` for preflight).
- A starting context — none, a local file, or an existing Context Store resource name. Entry flow spells out the handling per case.
- (Optional) Workspace root directory. Default: `.context-engineering/experiments/<experiment_name>/` at cwd.

## Guidance

Load `references/workspace.md` before any workspace interaction — it describes the internal iteration layout.

### Entry flow
1. **Locate workspace** at `<workspace_root>` (default `.context-engineering/experiments/<experiment_name>/`). Confirm the path with the user before creating it fresh — the directory holds every iteration's scratch state. If `state.md` exists → **resume** from the recorded iteration (see Resume rules in `references/workspace.md`). Otherwise → **fresh start**.
2. **Fresh start — seed v0.** Resolve the base context per Prerequisites:
   - **None** → invoke `context-engineering-bootstrap` to generate a local file, then upload as `v0` via `upload_context_set`.
   - **Local file** → upload as `v0` via `upload_context_set`.
   - **Existing Context Store resource name** → download the body to `v0/context_set_v0.json` via `download_context_set`; treat the resource as `v0` (no re-upload).

   Record the `v0` resource name and write initial `state.md`. Then seed `v0/`: ensure `context_set_v0.json` is on disk, evaluate into `v0/eval/`, record the baseline score. Iteration loop starts at `v1`.

### Per-iteration loop (`vN`)
1. **Prepare `vN/`**: append the `## In-Progress: vN` marker to `state.md`, create the iteration directory, and seed `context_set_vN.json`:
   - If `context_set_v(N-1).json` is on disk (normal case — the prior iteration wrote it), copy it.
   - Otherwise (first iteration seeded from a caller-supplied resource name, or resuming after a crash), call `download_context_set` on the `v(N-1)` resource name recorded in `state.md`.
2. **Evaluate**: invoke `context-engineering-evaluate` with `output_dir=<workspace>/vN/eval/`. Capture `job_id` and overall score.
3. **Analyze**: read `scores.csv` + `summary.csv` via `read_evaluation_result`; cluster failures by category; write findings + reasoning + planned mutations to `analysis_vN.md`.
4. **Mutate**: plan mutations from the analysis (prefer fewer general items — a facet often beats many templates). Author new items via `context-engineering-generation-guide`. Validate generated SQL via `<source>-execute-sql` and column references via `<source>-list-schemas`. Apply via `mutate_context_set` to `context_set_vN.json`.
5. **Upload**: call `upload_context_set` with `version="vN"`. Record the returned resource name.
6. **Update `state.md`**: replace the `## In-Progress: vN` marker with the final `### vN` entry (resource name, eval report path, analysis path, score).
7. **Check convergence** (see below). If not converged, continue to `v(N+1)`.

### Convergence
Iterate until you don't see new improvements. When stopping, append `## Converged: <one-line reason>` to `state.md` so a resume knows the run terminated intentionally.

The user can also explicitly ask to stop at any time; the current iteration completes cleanly, `## User Stop` is appended to `state.md`, and all iteration files are preserved.

**Final output** is the version with the highest recorded score.

## Rules
- The workspace is internal state; user-visible output is the final `cs_resource_name` and score. Do not surface intermediate iteration files as user deliverables.
- Only `Template`, `Facet`, `Value Search` types are emitted as mutations. Do not invent new item types.
- Avoid overfitting: mutations should generalize to unseen NLQs, not just fix specific failing golden pairs.
- Compose the sibling skills (`context-engineering-bootstrap`, `context-engineering-evaluate`, `context-engineering-generation-guide`); never re-implement their logic.
- Never require per-iteration user approval — the loop must run autonomously. Only pause on: convergence, error, or explicit user stop.
- Do not read the target ContextSet file directly for mutations; always use `mutate_context_set`.
- A full run is long — 10 iterations × multi-minute evaluations each can take 30–60+ minutes. Warn the user upfront and run in a session that tolerates long work.

## Tools

**Sibling skills:**
- `context-engineering-bootstrap` — cold-start path when no base context.
- `context-engineering-evaluate` — invoked once per iteration.
- `context-engineering-generation-guide` — produces well-formed Template / Facet / Value Search JSON.

**MCP:**
- `upload_context_set` → `cs_resource_name` — version push per iteration.
- `download_context_set` — seed on resume.
- `mutate_context_set` — apply planned mutations.
- `read_evaluation_result` — read scored eval reports.
- `<source>-list-schemas` (Toolbox) — validate that referenced columns exist.
- `<source>-execute-sql` (Toolbox) — validate that generated SQL runs against the DB.

**References:**
- `references/workspace.md` — internal workspace layout; load before any workspace interaction.
