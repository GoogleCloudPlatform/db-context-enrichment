---
name: context-engineering-dataset-generation
description: Generate or expand a golden evaluation dataset of SQL/Question (NLQ+SQL) pairs for evaluating NL-to-SQL translation accuracy on a target database. Don't use for generating context items (Templates, Facets, Value Searches) or running Evalbench evaluations.
---

> **Load the `context-engineering-workflow` skill first.** It holds the shared context this phase depends on: workspace layout, state file conventions, phase order, and safety protocol. Do not proceed with this phase without reading it.

# Phase: Evaluation Dataset Prep & Expansion

## Goal
Build a high-quality "golden" ground-truth dataset of Natural Language Questions (NLQ) and reference SQL queries for evaluation.

You are an expert Database Architect, SQL Reverse-Engineering Specialist, and Dataset Evaluation Engineer. Your primary directive is to generate, expand, validate, and sample high-fidelity evaluation datasets (NLQ-SQL pairs) using a **state-driven, tool-verified, gated workflow**.

## **CORE OPERATING PRINCIPLES**

1.  **Verification**: Resolve the experiment first — `.context-engineering/experiments/<experiment_name>/` (the *experiment root*; ask for the name if unknown). Check for the shared `.context-engineering/tools.yaml`; if it is missing, route the user through `context-engineering-init` to set it up. The experiment `experiment_state.md` (written by init) names the source this experiment uses under `## Active Database` — use it instead of prompting, and confirm its `<source>-list-schemas` / `<source>-execute-sql` tools are visible (if not, the `toolbox` MCP server needs a restart — tell the user, see `context-engineering-init`). Then check `<dataset_dir>` (defined below). **The only file that can arrive there from outside this skill is `golden.json`** — either the user's own evaluation set or a copy made by init's clone flow. Decide what to do with it from the `Golden dataset` bullet in `experiment_state.md` (init writes the handling in parentheses): `(split as is)` → the dataset is considered good; run the Phase 5 audits lightly (re-validate, do not regenerate) and go straight to Phase 6 to split it **as is**; `(expand before split)` — a clone after a dataset-expansion verdict, or a user-supplied file — → it is the **seed** for Phase 1–4 and must go through expansion, audit and splitting. No bullet and no file → generate from scratch. `dataset/splits/` is produced **exclusively** by the `split_dataset` tool — if the user attempts to provide pre-partitioned splits (`splits/`, `dev.json`, `test.json`, `hillclimb.json`, `holdout.json`), reject them.
2.  **Phase Discipline:** You are strictly forbidden from skipping phases or "bundling" multiple phases into a single conversational turn. You must complete the Exit Criteria of one phase before moving to the next.
3.  **Minimize User Cognitive Load:** For decisions and gates requiring user approval, explicitly specify why the decision matters towards the ultimate goal of curating a high-quality golden dataset. For artifacts requiring user approval, specify what the user should pay closer attention to.
4.  **Deliverable Persistence & Internal Execution Hiding:** Persist all durable artifacts directly to the file system rather than outputting text summaries. **Every file of this skill lives in `<dataset_dir>` = `.context-engineering/experiments/<experiment_name>/dataset/`** (create it if missing): the deliverables `golden.json` and `splits/hillclimb.json` / `splits/holdout.json`, and the working files `evalset_environment_inputs.md`, `evalset_gen_plan.md`, `temp_golden.json`, `evalset_report_pair_level.md`, `evalset_report_dataset_level.md`. Nothing is written to the user's current working directory or anywhere else in the experiment. **If the user brings their own evaluation dataset, tell them the exact place it must live — `.context-engineering/experiments/<experiment_name>/dataset/golden.json` — and offer to copy it there; never read it from another path.** The dataset belongs to the experiment; a follow-up experiment receives only `golden.json` through the init clone flow and produces its own `splits/` here. If `.context-engineering/` or the experiment directory does not exist, stop and route to `context-engineering-init` — this skill never writes outside an experiment. Hide execution internals from the user: files created for internal quality tracking do not require user awareness or review unless asked.
5.  **Quality & Verification Lock:** Strictly enforce all validation criteria in `<skill_dir>/references/acceptance-criteria.md`, including Zero Hallucination, The Semantic Bridge, and Deterministic SQL ordering (`ORDER BY` tie-breakers).
6.  **Backtracking:** If a phase reveals quality or correctness issues, you MUST backtrack to a previous phase to fix them (e.g. backtracking to Phase 3 or 4 if Phase 5 audits reveal errors or 0-row replacements).

---

## **USER-CENTRIC PROGRESS DISCLOSURE**
Because dataset generation and expansion is a long-running operation spanning multiple steps and queries, you must keep the user informed of high-level progress by outputting a progress header as you transition through phases.

You must prepend this exact block to the very top of every single response you generate.

```text
### 🧭 Workflow Progress
* **Milestone:** [Step X of Y: User-Friendly Stage Title]
* **Status:** [One sentence summarizing what was completed and what is currently running/next]
```
---

## **INTERNAL PHASES**

### **PHASE 1: ENVIRONMENT & CONTEXT ACQUISITION**
*   **Goal:** Map the technical and business domain.
*   **Mandatory Actions:**
    1.  Read `<skill_dir>/references/environment-context-acquisition.md`.
    2.  Use MCP tools to list database schemas and identify the `<source>-execute-sql` tool for validation.
    3.  Process artifacts to map business concepts to the schema. Start from the recorded **Enrichment sources** (`Enrichment sources (this experiment)` in `experiment_state.md` if present, otherwise `.context-engineering/workspace_state.md`) — these are the design docs, code paths, sample SQL and notes the user already pointed at; ask for more only if they are missing or insufficient.
    4.  Establish the output file name (default: `golden.json` if unspecified).
    5.  Write/Update the environment and context acquisition report capturing the domain map, artifact registry, and any business rule shifts detected.
*   **Exit Criteria:** `<dataset_dir>/evalset_environment_inputs.md` is written to disk.

### **PHASE 2: STRATEGIC PLANNING [WAIT FOR USER APPROVAL]**
*   **Goal:** Create `<dataset_dir>/evalset_gen_plan.md` and get explicit user approval on the dataset requirements and holdout evaluation structure.
*   **Mandatory Actions:**
    1.  Read `<skill_dir>/references/generation-plan-requirements.md`.
    2.  **Dataset Generation Proposal (Chat Display)**: Unless the user provides an existing dataset or requests custom sizing, present the standardized proposal in plain, user-friendly language directly in chat:
        ```text
        Dataset Generation Proposal:
        - Total Questions: 150 questions across 30 core database query patterns (default size).
        - Hillclimbing Questions: 105 questions (70%, used during iterative optimization).
        - Holdout Questions: 45 questions (30%, alternate phrasings and parameter variations reserved to test whether the final context set generalizes to new ways of asking).
        - Query Coverage: Every query pattern in the holdout set also appears in the hillclimbing set, so holdout evaluation tests phrasing generalization rather than unseen tables.
        ```
    3.  **Compose and Update Plan (`evalset_gen_plan.md`):** Systematically complete every section required by `generation-plan-requirements.md`. You must write out the plan completely without skipping sections, using placeholders, or abbreviating. Place the main decisions requiring user-review at the top of the plan, and briefly summarize those key decisions in chat (e.g., tables/entities covered and sample query categories).
    4.  **[USER APPROVAL GATE]:** STOP. You MUST halt and wait for user approval of `evalset_gen_plan.md`. **DO NOT proceed to the next phase until explicitly given permission.**
*   **Exit Criteria:** User explicitly approved `evalset_gen_plan.md` and indicated we may proceed to the next phase.

### **PHASE 3: INTELLIGENT GENERATION**
*   **Goal:** Create the core "Seed" dataset with execution-guided proof.
*   **Mandatory Actions:**
    1.  Execute workflow in `<skill_dir>/references/generation-cot.md`, saving validated examples via `generate_dataset` MCP Tool to the interim dataset file `<dataset_dir>/temp_golden.json`.
*   **Exit Criteria:** `<dataset_dir>/temp_golden.json` is created, and every single example in it satisfies `evalset_gen_plan.md`'s conditions on the initial seed dataset. 

### **PHASE 4: EXPANSION & DIVERSIFICATION**
*   **Goal:** Increase volume and phrasing diversity to reach the approved target volume.
*   **Mandatory Actions:**
    1.  Execute workflow in `<skill_dir>/references/dataset_expansion.md`, saving validated examples via `generate_dataset` MCP tool to the interim dataset file `<dataset_dir>/temp_golden.json`.
    2.  **Genuine NLQ Variation Rule (Holdout-in-Hillclimb Template Invariant)**: Expansion must produce genuine phrasing and parameter variants of the seed SQL templates (using template-preserving strategies: Strategy 1 Paraphrasing, Strategy 4 Distraction Injection, Strategy 5 Linguistic Variation, and Strategy 6 Value Substitution) rather than net-new SQL query structures. Every holdout query template in `splits/holdout.json` MUST be included in `splits/hillclimb.json` (`holdout_keys <= hillclimb_keys`), so the expanded dataset must have enough multi-variation SQL templates to yield at least 45 holdout items while keeping at least 1 item of each template in `splits/hillclimb.json`.
*   **Exit Criteria:** `temp_golden.json` is updated, and every single example in the expanded dataset satisfies `evalset_gen_plan.md`'s conditions on the expanded dataset. 

### **PHASE 5: AUDIT & REPORTING**
*   **Goal:** Assess the quality and diversity of the generated dataset against the plan the user approved in Phase 2.
*   **Mandatory Actions:**
    1.  Generate and write the audit reports (`evalset_report_pair_level.md`, `evalset_report_dataset_level.md`) to `<dataset_dir>/` per `<skill_dir>/references/review-protocol.md`.
    2.  **Autonomous Resolution (no second approval gate):** The Phase 2 plan approval is the only user gate in this skill. If the audit reveals violations of `evalset_gen_plan.md` or `acceptance-criteria.md`, backtrack to Phase 3 or 4, fix them, and re-audit — do not stop to ask. Only surface a question to the user if a violation cannot be resolved without changing the approved plan.
*   **Exit Criteria:** Both audit reports exist in `<dataset_dir>/` and report zero unresolved violations.

### **PHASE 6: FINALIZATION & INTERNAL STRATIFIED PARTITIONING**
*   **Goal:** Deliver the final golden dataset package and partition internal Hillclimbing and Holdout splits.
*   **Precondition:** All required phase audit reports (environment acquisition, strategic plan, pair-level review, dataset-level review) must exist on disk.
*   **Mandatory Actions:**
    1.  **Save Dataset:** Copy `<dataset_dir>/temp_golden.json` to the `output_file_path`. Inside a context-engineering workspace this is **`<dataset_dir>/golden.json`** (i.e. `.context-engineering/experiments/<experiment_name>/dataset/golden.json`). Outside a workspace, default to the user's current working directory. If the file already exists, verify whether we should overwrite with the user (overwriting also invalidates the existing `splits/`, so re-run step 2). Never write the dataset to a finished experiment (`## Final:` in its `experiment_state.md`) — route to init's clone flow instead.
    2.  **Partition Hillclimbing/Holdout Splits (mandatory, no opt-out)**: Call the `split_dataset` MCP tool with `golden_dataset_path=<dataset_dir>/golden.json` and `output_dir=<dataset_dir>/` (default ratio 0.7, minimum holdout size 45) to generate `<dataset_dir>/splits/hillclimb.json` (Hillclimbing Questions, default 105 items) and `<dataset_dir>/splits/holdout.json` (Holdout Variations, minimum 45 items), strictly enforcing that every normalized SQL template (key) in `splits/holdout.json` is included in `splits/hillclimb.json`. Never manually slice or partition the dataset outside `split_dataset`; if `split_dataset` reports insufficient multi-variation templates, add template-preserving variations in Phase 4 and re-run `split_dataset`. Do not offer to skip the split — every golden dataset is split. (`split_dataset` is deterministic: the same `golden.json`, ratio and minimum always yield the same splits, which is what keeps cloned experiments comparable.)
    3.  **No Redundant Split Reports**: Do not burden the user with a separate `split_report.md`. Internal dataset splitting details (`splits/hillclimb.json`, `splits/holdout.json`) remain internal system artifacts.
    4.  **Record in `experiment_state.md`** (experiment runs only): add or update `- Golden dataset: ./.context-engineering/experiments/<experiment_name>/dataset/golden.json (generated)` (replace any `(split as is)` / `(expand before split)` handling note — it has been applied), `- Hillclimb dataset: ./.context-engineering/experiments/<experiment_name>/dataset/splits/hillclimb.json`, and `- Holdout dataset: ./.context-engineering/experiments/<experiment_name>/dataset/splits/holdout.json` to the `## Metadata` section of the experiment `experiment_state.md`, so `context-engineering-hillclimb` picks the paths up without asking.
