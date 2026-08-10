---
name: context-engineering-hillclimb
description: Guides the agent to perform generalizable hill-climbing iterations on a stratified Dev split to improve a ContextSet while measuring dev accuracy during hill climbing and evaluating holdout test set generalizability towards the end.
---

> **Load the `context-engineering-workflow` skill first.** It holds the shared context this phase depends on: workspace layout, state file conventions, phase order, and safety protocol. Do not proceed with this phase without reading it.

# Phase: Optimization & Generalizable Hill-Climbing

## Goal
Analyze evaluation failures on training/dev splits to perform Gap Analysis and apply targeted context mutations, while **measuring and guaranteeing generalizability** across held-out business subdomains, linguistic styles, complexity tiers, and logic depths.

---

## Generalizability & Validation Protocol

> [!IMPORTANT]
> **Generalizability Mandate**: Optimizing context on 100% of a synthetic evaluation dataset risks "echo chamber" overfitting (creating hyper-specific templates that fail on unseen user questions). To ensure context mutations generalize:
> 1. **Stratified Initial Split**: Perform dataset splitting **ONCE at the beginning** of hill-climbing using **Stratified Splitting** (`split_dataset` with `stratify_by="subdomain"` or `"complexity_tier"`).
> 2. **Stratum Adequacy Verification**: Review stratum volume warnings returned by `split_dataset`. If any stratum has fewer than 5 pairs, notify the user so they can optionally expand under-represented subdomains using `context-engineering-dataset-generation`.
> 3. **Hill-Climbing Iterations**: All iterative Gap Analysis, Context Mutations, and progress verification evaluations are performed using **ONLY the Dev split** (`dev.json`).
> 4. **Holdout Verification Towards the End**: Towards the end of the hill-climbing process (when Dev score targets are met or iterations complete), run evaluation on the held-out **Test split** (`test.json`) using the final improved context set. Use the `evaluate_generalizability` MCP tool to calculate the **Out-of-Domain Transfer Index (OOD-TI)**, **Linguistic Robustness Score (LRS)**, and **Generalization Gap** across dimension buckets.

---

## Stratified Hill-Climbing Workflow

Follow these steps in order:

### 1. Dataset Setup & Partitioning (At Start)
1. Check if `autoctx/experiments/<experiment_name>/splits/` already contains `dev.json` and `test.json`.
2. If missing, **ask the user before proceeding to dev-test split**:
   > *"Do you have an existing test dataset file you would like to use to evaluate generalizability at the end of the hill-climbing process?"*

   - **Case A: User Has a Custom Test Dataset**:
     - Prompt the user to provide the file path to their custom test dataset.
     - Copy and enrich their test dataset to `autoctx/experiments/<experiment_name>/splits/test.json`.
     - Use the generated evaluation dataset (`golden.json`) as `autoctx/experiments/<experiment_name>/splits/dev.json`.
   - **Case B: User Does Not Have a Custom Test Dataset**:
     - Automatically partition `golden.json` into a Stratified Dev/Test split (80% Dev / 20% Holdout Test stratified by `metadata.subdomain` or `complexity_tier`):
       - Group items in `golden.json` by `metadata.subdomain` (or `"general"` if absent).
       - For each subdomain bucket with $N \ge 2$ items, assign 80% (at least 1 item) to `dev.json` and remaining items to `test.json`.
       - For single-item subdomains ($N = 1$), assign to `dev.json` to ensure training coverage.
       - Save the items to `autoctx/experiments/<experiment_name>/splits/dev.json` and `splits/test.json`.
3. **Stratum Volume Check**:
   - Count items per subdomain bucket across Dev and Test sets.
   - If any subdomain has fewer than 5 evaluation pairs, inform the user:
     > *"Note: Subdomains [list] have fewer than 5 evaluation pairs. Holdout test evaluation will proceed, but expanding pairs for these subdomains via `context-engineering-dataset-generation` is recommended for robust test coverage."*
4. Confirm that `dev.json` and `test.json` are materialized on disk so that the workspace folder structure remains identical in either case.

### 2. Hill-Climbing Iteration Loop (Dev Set Only)
For each iteration ($v1, v2, \dots, vN$):

1. **Determine Loop Version**: Scan `autoctx/experiments/<experiment_name>/hillclimb/` for `improved_context_v*.json` (start at `v1` if empty).
2. **Locate Base Context**: For `v1`, default to `bootstrap_context.json`. For `vN` ($N > 1$), use `improved_context_v(N-1).json`.
3. **Gap Analysis (Dev Set)**:
   - Use `read_evaluation_result` on the Dev set evaluation run folder.
   - Analyze failure cases in batches (offset 0, 10, 20...). Categorize errors (`FilterError`, `OrderingError`, `SchemaError`, `GoldenDataError`).
   - Propose mutations emphasizing **generalizability** (prefer `facet` over narrow `template` where possible).
   - Write report to `autoctx/experiments/<experiment_name>/hillclimb/gap_analysis_vN.md`.
4. **Context Mutation**:
   - Copy base context to `autoctx/experiments/<experiment_name>/hillclimb/improved_context_vN.json`.
   - Generate required new items following [context-generation-guide](../context-generation-guide/SKILL.md).
   - Validate SQL syntax via `<source>-execute-sql`.
   - Call `mutate_context_set` MCP tool to apply mutations.
5. **Dev Set Verification Evaluation**:
   - Execute evaluation on `splits/dev.json` using `improved_context_vN.json`.
   - Verify Dev score improvement. Repeat the hill-climbing loop as needed on `dev.json`.

### 3. Test Split Evaluation & Generalizability Verification (Towards the End)
Towards the end of the hill-climbing process (when Dev performance target is met or iterations conclude):

1. **Execute Holdout Test Evaluation**: Run evaluation on `splits/test.json` using the final `improved_context_vN.json`.
2. **Calculate Generalizability Metrics**:
   - Compare final Dev evaluation scores vs Holdout Test evaluation scores.
   - Calculate **Dev Pass Rate (%)** vs **Holdout Test Pass Rate (%)**.
   - Calculate **Generalization Gap**: $\text{Dev Score} - \text{Holdout Score}$.
   - Calculate **Out-of-Domain Transfer Index (OOD-TI)**: $\text{Test Score} / \text{Dev Score}$.
   - Calculate **Linguistic Robustness Score (LRS)**: Jargon query test pass rate vs canonical dev pass rate.
3. **Present Generalizability Metrics Report**:
   Present the report containing:
   - **Dev Pass Rate (%)** vs **Holdout Test Pass Rate (%)**
   - **Generalization Gap** & **Out-of-Domain Transfer Index (OOD-TI)**
   - **Linguistic Robustness Score (LRS)**
   - **Dimension Breakdown Matrix** across subdomains, linguistic styles, and complexity tiers.

---

## Validation & Upload Advice

1. Summarize improvements and report Dev Score, Holdout Score, OOD-TI, and LRS.
2. Provide upload link via `generate_upload_url`.

---

## State Logging Example (`autoctx/state.md`)

```markdown
# Context Authoring Experiment State Tracking

## Active Experiment: my-exp-1

## Hill-Climbing Run Log

### Loop: v1 (Stratified Mode)
- **Split Mode**: Stratified by Subdomain (80/20)
- **Dev Set**: `autoctx/experiments/my-exp-1/splits/dev.json` (40 items)
- **Holdout Test Set**: `autoctx/experiments/my-exp-1/splits/test.json` (10 items)
- **Dev Pass Rate**: 90.0%
- **Holdout Test Pass Rate**: 82.5% (Verified towards end of hillclimbing)
- **Generalization Gap**: +7.5%
- **Out-of-Domain Transfer Index (OOD-TI)**: 0.91 ✅
- **Linguistic Robustness Score (LRS)**: 0.88 ✅
- **Gap Analysis**: `autoctx/experiments/my-exp-1/hillclimb/gap_analysis_v1.md`
- **Mutated Context**: `autoctx/experiments/my-exp-1/hillclimb/improved_context_v1.json`
```

> [!IMPORTANT]
> **Tool Modification Rule**: Always use the `mutate_context_set` tool for all ContextSet changes.
