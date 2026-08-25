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
> 1. **Stratified Split Verification**: Verify that the Stratified Dev/Test split (`dev.json` and `test.json`) created during the dataset generation phase is present under `autoctx/experiments/<experiment_name>/splits/`. If missing, run the `split_dataset` MCP tool to partition `golden.json`.
> 2. **Stratum Adequacy Verification**: Review stratum volume warnings from dataset generation / `split_dataset`. If any stratum has fewer than 5 pairs, notify the user so they can optionally expand under-represented subdomains using `context-engineering-dataset-generation`.
> 3. **Hill-Climbing Iterations**: All iterative Gap Analysis, Context Mutations, and progress verification evaluations are performed using **ONLY the Dev split** (`dev.json`).
> 4. **Mandatory File Persistence for Generalization Report**: Towards the end of the hill-climbing process (when Dev score targets are met or iterations complete), run evaluation on the held-out **Test split** (`test.json`) using the final improved context set. You MUST write and persist a comprehensive, descriptive report directly to disk at `autoctx/experiments/<experiment_name>/hillclimb/final_evaluation_report.md` focusing primarily on the **Generalization Gap** ($\text{Dev Score} - \text{Holdout Score}$) and qualitative failure analysis (identifying where the context does not work well), using Out-of-Domain Transfer Index (OOD-TI) and Linguistic Robustness Score (LRS) as reference diagnostic metrics. Do not merely print the report in chat; it must always be persisted to disk.

---

## Stratified Hill-Climbing Workflow

Follow these steps in order:

### 1. Dataset Split Verification & Experiment Selection
1. Select or confirm the active experiment folder under `autoctx/experiments/<experiment_name>/`.
2. Check if `autoctx/experiments/<experiment_name>/splits/` already contains `dev.json` and `test.json` (generated in the final step of dataset generation).
3. **If missing** (e.g. user provided an external `golden.json` without running dataset generation finalization):
   - Ask the user if they have an existing custom test dataset file for holdout testing.
   - Invoke the `split_dataset` MCP tool:
     - `golden_dataset_path`: Path to `golden.json`.
     - `output_dir`: `autoctx/experiments/<experiment_name>/`
     - `custom_test_dataset_path`: Optional path if provided by the user.
     - `stratify_by`: `"subdomain"` (or `"complexity_tier"`).
4. Review stratum item counts and confirm `dev.json` and `test.json` are materialized on disk.
5. Proceed directly to the Dev set hill-climbing iteration loop using `splits/dev.json`.

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

### 3. Holdout Test Evaluation & Descriptive Generalization Report (Towards the End)
Towards the end of the hill-climbing process (when Dev performance target is met or iterations conclude):

1. **Execute Holdout Test Evaluation**: Run evaluation on `splits/test.json` using the final `improved_context_vN.json`.
2. **Analyze Generalization Gap (Primary Focus)**:
   - Compare final Dev evaluation scores vs Holdout Test evaluation scores.
   - Calculate **Dev Pass Rate (%)** vs **Holdout Test Pass Rate (%)**.
   - Calculate **Generalization Gap ($\Delta_{\text{gen}}$)**: $\text{Dev Score} - \text{Holdout Score}$.
   - Identify specific subdomains, complexity tiers, linguistic styles, or business concepts where performance drops significantly on unseen queries.
   - Deep-dive into each failed holdout test query using `read_evaluation_result`:
     - Compare NLQ, Expected SQL, and Generated SQL.
     - Diagnose why the context failed to generalize (e.g. overfitted template pattern, missing facet constraint, unrecognized jargon/synonym, unparameterized literal).
3. **Compute Reference Diagnostic Metrics**:
   - **Out-of-Domain Transfer Index (OOD-TI)**: $\text{Holdout Score on Unseen Subdomains} / \text{Dev Score}$ (reference indicator for cross-module transfer).
   - **Linguistic Robustness Score (LRS)**: $\text{Holdout Score on Jargon Queries} / \text{Dev Score on Canonical Queries}$ (reference indicator for phrasing variations).
   *(Note: OOD-TI and LRS are reference diagnostic metrics for additional context, not hard pass/fail targets).*
4. **Mandatory Report File Persistence (`final_evaluation_report.md`)**:
   You MUST write and persist the complete report directly to disk at `autoctx/experiments/<experiment_name>/hillclimb/final_evaluation_report.md`. Confirm the file exists on disk before concluding the run or presenting findings to the user. Follow this structure:

   ```markdown
   # Final Evaluation & Generalization Report

   ## 1. Executive Summary
   - **Tuned Context**: `autoctx/experiments/<experiment_name>/hillclimb/improved_context_vN.json`
   - **Dev Set Pass Rate**: `XX.X%` (N queries)
   - **Holdout Test Pass Rate**: `XX.X%` (M queries)
   - **Generalization Gap ($\Delta_{\text{gen}}$)**: `+X.X%` (Dev - Holdout)
   - **Reference Diagnostic Indicators**:
     - **Out-of-Domain Transfer Index (OOD-TI)**: `X.XX` (Reference metric for cross-module transfer)
     - **Linguistic Robustness Score (LRS)**: `X.XX` (Reference metric for phrasing robustness)

   ## 2. Generalization Gap Analysis (Where It Does Not Work Well)
   - **High-Risk Subdomains / Concepts**: Detailed breakdown of subdomains where test accuracy lagged behind dev accuracy.
   - **Linguistic / Complexity Weaknesses**: Failure patterns observed on complex joins, aggregations, or conversational jargon.
   - **Overfitting Diagnostics**: Analysis of whether specific templates were tuned too narrowly to training query phrasing.

   ## 3. Holdout Test Failure Case Deep-Dive
   | Query ID | Subdomain | Natural Language Query | Failure Diagnosis & Root Cause |
   | :--- | :--- | :--- | :--- |
   | `eval_test_03` | `billing` | "Show unpaid invoices over 90 days" | Missing facet for status filter; generated SQL missed `status = 'OVERDUE'`. |
   | `eval_test_07` | `sales` | "Top 5 reps by Q3 quota attainment" | Overfitted template expected explicit date range instead of quarter shorthand. |

   ## 4. Key Recommendations & Next Steps
   - Actionable advice for future context authoring (e.g., adding facets for status filters, expanding synonyms).
   - Dataset expansion recommendations for under-tested subdomains.
   ```

---

## Validation & Upload Advice

1. Summarize final results with the user, highlighting the Dev Score, Holdout Score, Generalization Gap, and presenting the findings from `final_evaluation_report.md`.
2. Provide upload link via `generate_upload_url`.

---

## State Logging Example (`autoctx/state.md`)

```markdown
# Context Authoring Experiment State Tracking

## Active Experiment: my-exp-1

## Hill-Climbing Run Log

### Loop: v1 (Stratified Mode)
- **Dev Set**: `autoctx/experiments/my-exp-1/splits/dev.json` (40 items)
- **Holdout Test Set**: `autoctx/experiments/my-exp-1/splits/test.json` (10 items)
- **Dev Pass Rate**: 90.0%
- **Holdout Test Pass Rate**: 82.5% (Verified on held-out test split)
- **Generalization Gap**: +7.5%
- **Reference Indicators**: OOD-TI = 0.91, LRS = 0.88 (Informational)
- **Gap Analysis**: `autoctx/experiments/my-exp-1/hillclimb/gap_analysis_v1.md`
- **Mutated Context**: `autoctx/experiments/my-exp-1/hillclimb/improved_context_v1.json`
- **Final Evaluation Report**: `autoctx/experiments/my-exp-1/hillclimb/final_evaluation_report.md`
```

> [!IMPORTANT]
> **Tool Modification Rule**: Always use the `mutate_context_set` tool for all ContextSet changes.
