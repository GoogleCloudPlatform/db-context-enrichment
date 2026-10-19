# Holdout Evaluation & Generalization Reporting Phase

## Overview & Entry Prerequisites

*   **Automatic Entry Trigger**: Invoked by `context-engineering-hillclimb` **Finalize step 3**, immediately after the optimization loop stops (tuning target, plateau, or iteration cap) and the best iteration `vK` has been placed in the **working copy** (`## Finalizing: vK` present in `experiment_state.md`). It runs **before** any existing context set is replaced, so a poor verdict never costs the user their previous version. Preempts any further optimization loops. Not triggered after a `## User Stop`.
*   **Goal**: Zero additional user-facing steps. Evaluates the **candidate** — the working copy: the bare `<context_set_id>` in the fresh case, `<context_set_id>_draft` in the existing case — on `splits/holdout.json` strictly once in a single read-only pass, executes the two-proportion pooled z-test via `evaluate_generalizability`, writes `final_evaluation_report.md` and `## Generalizability`, and hands the verdict back to hillclimb Finalize (step 4) which decides the publication state; the On-Screen Card is printed after that decision.
*   **Zero-Leakage Invariant**: The holdout partition (`splits/holdout.json`) is strictly isolated during the entire hill-climbing optimization loop (zero data leakage). It must never be accessed for gap analysis, candidate selection, error harvesting, or context mutation. It is evaluated strictly once at workflow conclusion.
*   **Entry Prerequisites**:
    *   [ ] **Candidate in place**: `experiment_state.md` contains `## Finalizing: vK` and the working copy's last upload (of `vK`) has reported `done: true`.
    *   [ ] **Holdout Precondition Met**: `.context-engineering/experiments/<experiment_name>/dataset/splits/holdout.json` (the `Holdout dataset` recorded in `experiment_state.md`) exists. It always does when the dataset came through `context-engineering-dataset-generation` (the split is mandatory); if it is missing, stop and route to that skill — do not report a verdict without it.

---

## Workflow & Execution Steps

1.  **Single Read-Only Holdout Evaluation (Autonomous Zero-Prompt Execution)**:
    *   **Do NOT Prompt or Ask Permission**: Reuse `experiment_name`, `toolbox_config_path` (`.context-engineering/tools.yaml`), `toolbox_source_name` (**Source Name** from `## Active Database` in `experiment_state.md`), and the **candidate's** resource string — `Final Context Set resource` when `Draft Context Set resource` is `(none …)`, otherwise `Draft Context Set resource` — exactly as recorded in `experiment_state.md`, without asking the user for any parameters or confirmation.
    *   **Generate Holdout Evalbench Configs**: Immediately call the `generate_evalbench_configs` MCP tool with `output_dir=".context-engineering/experiments/<experiment_name>/hillclimb/holdout_eval/"`, `dataset_path=".context-engineering/experiments/<experiment_name>/dataset/splits/holdout.json"`, and the candidate resource string as `context_set_id`, plus `toolbox_config_path` and `toolbox_source_name`.
    *   **Run Holdout Evaluation**: Immediately execute the canonical Evalbench command:
        `uvx google-evalbench@1.18.0 --experiment_config=.context-engineering/experiments/<experiment_name>/hillclimb/holdout_eval/eval_configs/run_config.yaml`
    *   **Extract Scores**: Extract `test_passed` and `test_total` from `holdout_eval/eval_reports/<job_id>/summary.csv`, and retrieve `dev_passed` and `dev_total` from the candidate iteration's (`vK`) entry in the `experiment_state.md` Iteration Log.

2.  **Statistical Significance Testing (Two-Proportion Pooled z-Test)**:
    *   Call the `evaluate_generalizability` tool with `dev_passed`, `dev_total`, `test_passed`, `test_total`, `alpha=0.05`, and the candidate's resource string as `context_set_id`.
    *   **Statistical Formulation**:
        *   $p_{\text{dev}} = \frac{x_{\text{dev}}}{N_{\text{dev}}}$, $p_{\text{test}} = \frac{x_{\text{test}}}{N_{\text{test}}}$
        *   $p_{\text{pool}} = \frac{x_{\text{dev}} + x_{\text{test}}}{N_{\text{dev}} + N_{\text{test}}}$
        *   $SE = \sqrt{p_{\text{pool}}(1 - p_{\text{pool}})\left(\frac{1}{N_{\text{dev}}} + \frac{1}{N_{\text{test}}}\right)}$
        *   $z = \frac{p_{\text{dev}} - p_{\text{test}}}{SE}$, $p\text{-value} = 2(1 - \Phi(|z|))$
    *   **Directional Decision Logic**:
        *   **INCONCLUSIVE**: $N_{\text{test}} < 45$ (underpowered sample size).
        *   **INVESTIGATE**: $p < 0.05$ AND $p_{\text{dev}} > p_{\text{test}}$ (statistically significant drop indicating overfitting to hillclimbing wording).
        *   **PASS**: $p \ge 0.05$ with $N_{\text{test}} \ge 45$, OR $p_{\text{test}} \ge p_{\text{dev}}$ (no statistically significant drop; context generalizes reliably).

3.  **Agent On-Screen Interface (Primary Chat Output)**:
    *   **Core Principle**: The chat card is the primary user interface. Novice users should never be required to open a markdown file to understand the verdict, performance, or next steps.
    *   **Order by Decision Relevance**: Status & Verdict $\rightarrow$ Performance Overview (4-column table) $\rightarrow$ Plain-Language Summary & Diagnosis $\rightarrow$ Immediate Next Step (including the **full published `context_set_id`** resource name when ready for production).
    *   **Plain-Language Terminology**: Use "Hillclimbing Questions" and "Holdout Questions" (not ML jargon). Explain differences humanely (e.g. `Difference: -3.8% (within expected variance)`). Restrict formulas, z-scores, and p-values to `final_evaluation_report.md`.
    *   **On-Screen Card Templates**:

        *   **Case 1: PASS — Ready for Production**:
            ```markdown
            🎯 **Evaluation Complete: Context Set Generalizes Reliably**

            **Status**: Ready for Production

            Your context set successfully handles unseen phrasings and parameter variations across the covered query patterns without performance drops.

            | Split | Accuracy | Correct Queries | Notes |
            | :---- | :---: | :---: | :---- |
            | **Hillclimbing Questions** | **90%** | **95 / 105** | **Baseline optimization accuracy** |
            | **Holdout Questions** | **87%** | **39 / 45** | **Consistent with hillclimbing** |

            **Summary**:
            * **Robustness**: The model generalizes well to new phrasings and literal values across the covered query patterns rather than memorizing exact hillclimbing questions. The minor difference between hillclimbing and holdout (87% vs 90%) is well within normal statistical expectations.
            * **Next Step**: <fresh case: "The context set is live at `<Final Context Set resource>` (from iteration `vK`, local file `vK/context_set_vK.json`). Point your application at it." | existing case, replaced: "`<Final Context Set resource>` now holds this version (from `vK`); the previous contents are kept in `v0/context_set_v0.json`." | existing case, kept: "`<Final Context Set resource>` was left unchanged; the candidate is in `vK/context_set_vK.json`."> No further optimization iterations required.
            ```

        *   **Case 2: INCONCLUSIVE — Sample Size Too Small**:
            ```markdown
            ⚠️ **Evaluation Inconclusive: Sample Size Too Small**

            **Status**: More Data Needed

            The holdout set is too small to determine whether the context set generalizes reliably.

            | Split | Accuracy | Correct Queries | Notes |
            | :---- | :---: | :---: | :---- |
            | **Hillclimbing Questions** | **90%** | **36 / 40** | **Baseline optimization accuracy** |
            | **Holdout Questions** | **80%** | **8 / 10** | **2 failures; sample size underpowered** |

            **Summary & Recommendation**:
            * **Diagnosis**: With only 10 holdout questions, each question changes accuracy by 10%. A statistical test cannot distinguish normal variation from genuine performance drops.
            * **Recommended Action**: **Expand Evaluation Dataset** to at least **150 total questions** (>= 105 Hillclimbing / >= 45 Holdout) in a new cloned experiment — use the copy-paste prompt under **Next step** below.
            ```

        *   **Case 3: INVESTIGATE — Performance Drop on Holdout Questions**:
            Inspect the holdout failure breakdown (step 4) to identify whether the dominant failures come from **Path A (Context & Metadata Gaps — missing business-rule Facets or unmapped enum/synonym Value Searches)** or **Path B (Question Phrasing & Curriculum Gaps — informal wording, acronyms, or shorthand not represented in the dataset)**, and show the specific diagnosed recommendation rather than a generic menu:
            ```markdown
            ❌ **Evaluation Alert: Performance Drop on Holdout Questions**

            **Status**: Needs Optimization (Gaps Identified)

            The model passed hillclimbing questions but dropped on holdout phrasings due to missing context definitions or unseen phrasing patterns.

            | Split | Accuracy | Correct Queries | Notes |
            | :---- | :---: | :---: | :---- |
            | **Hillclimbing Questions** | **92%** | **97 / 105** | **Baseline optimization accuracy** |
            | **Holdout Questions** | **71%** | **32 / 45** | **Significant drop (-21% across 13 queries)** |

            **Summary & Recommendation**:
            * **Diagnosis**: <X> of <Y> holdout failures (<Z>%) occurred because of <plain-language root cause from the failure breakdown, e.g., unmapped status/enum values and missing business-rule filters | informal phrasing and shorthand not covered in the dataset>.
            * **Recommended Action**: <If Path A (Context Fixes): "**Add Business-Rule Facets / Value Searches** for <specific gaps> while keeping the same dataset splits so the before/after scores are directly comparable." | If Path B (Dataset Expansion): "**Expand Question Phrasings in the Dataset** to cover <specific informal phrasing/acronyms/patterns> and re-run optimization."> Use the copy-paste prompt under **Next step** below to start a cloned experiment.
            ```

4.  **Save Final Evaluation Report (`final_evaluation_report.md`)**:
    *   Write the comprehensive audit report to `.context-engineering/experiments/<experiment_name>/hillclimb/final_evaluation_report.md`.
    *   Ordered strictly by decision relevance (Verdict & Status $\rightarrow$ Recommended Action / Next Steps $\rightarrow$ Performance Overview & Failure Breakdown $\rightarrow$ Statistical Details):
        *   `TL;DR`: Verdict, Next Steps, Generalization Drop, Significance Assessment, Summary.
        *   `1. ACTIONABLE RECOMMENDATIONS`: Concrete recommended action and next steps for the user placed at the top.
        *   `2. PERFORMANCE OVERVIEW`: Table and counts for hillclimbing vs holdout, difference note, pattern coverage.
        *   `3. HOLDOUT SET FAILURE BREAKDOWN`: Query-by-query breakdown of failed holdout cases with category and root cause.
        *   `4. STATISTICAL DETAILS`: Two-proportion pooled z-test, sample sizes ($N_{\text{dev}}, x_{\text{dev}}, N_{\text{test}}, x_{\text{test}}$), pooled proportion ($\hat{p}$), standard error ($SE$), test statistic ($z$), two-tailed $p$-value, and power analysis check placed at the bottom.

5.  **Log State Tracking (`experiment_state.md`) and hand back**:
    *   Append a `## Generalizability` section to `.context-engineering/experiments/<experiment_name>/hillclimb/experiment_state.md` recording the holdout evaluation path (`holdout_eval/eval_reports/<job_id>/`), the candidate resource evaluated, holdout score (`passed / total`), the verdict (`PASS`, `INVESTIGATE`, or `INCONCLUSIVE`), and the report path. See the example in `context-engineering-hillclimb/references/layout.md`.
    *   **Return to `context-engineering-hillclimb` Finalize step 4**, which sets the publication state (fresh: already live; existing: the replace-or-keep HITL) and writes `## Final:`. Only then is the experiment **finished and read-only**. The On-Screen Card (step 3) and the hand-off (step 6) are printed after `## Final:` is written, so they can state where the context set actually is.

6.  **Next Experiment Hand-off (same turn, after the On-Screen Card — for INVESTIGATE and INCONCLUSIVE only)**:
    *   **PASS → no card.** The context set is production-ready and nothing needs doing; a clone card here only confuses. End with one line: *"If you later want to extend coverage or push accuracy further, say so and I'll start a new experiment cloned from `<experiment_name>`."*
    *   **Why a new experiment for the other verdicts**: a finished experiment is the frozen record of one run. Applying the report's recommendations *inside* it would change the published context set and make the before/after scores incomparable. Every follow-up therefore happens in a **new experiment cloned from this one**.
    *   **What the clone carries over is always the same: `dataset/golden.json` only.** The new experiment produces its own `splits/` with `split_dataset` (deterministic — an unchanged `golden.json` gives identical splits, so verdicts stay comparable). The verdict decides what happens to that file first (tell the user which applies):
        | Verdict / path | What the dataset skill does with the copied `golden.json` | Why |
        | :--- | :--- | :--- |
        | **INVESTIGATE — Path A** (context gaps: facets / value searches / templates) | re-validate and split **as is** | the dataset is fine; identical splits keep the new verdict comparable with this one |
        | **INVESTIGATE — Path B** (phrasing diversity) and **INCONCLUSIVE** (dataset too small) | **expand** it first, then split | the dataset itself must change; plan, reports and splits are regenerated in the new experiment |
    *   **Seed**: the new experiment starts from this experiment's result — the published `Final Context Set resource` when it was published, otherwise the best local file `vK/context_set_vK.json` — as `Seed Context Set resource` of the clone (read once, never overwritten). Its own `Context set id` defaults to the new experiment name (a fresh context set). The clone uses the **same `tools.yaml` source** (`## Active Database` is carried over; `tools.yaml` itself is shared and is not copied).
    *   **Print this card** (fill every placeholder; keep the prompt on one line so it can be copy-pasted):
        ```markdown
        ### Next step: start a new experiment
        `<experiment_name>` is complete and frozen (<"published: `<Final Context Set resource>`" | "not published; best candidate `vK/context_set_vK.json`">, verdict: **<VERDICT>**).
        Do not hill-climb it again — apply the recommendations in a **new experiment** so the two runs stay comparable.

        The new experiment will be cloned from this one:
        * database → same `tools.yaml` source: `<Source Name>` (no connection setup needed)
        * project, location, upload approval → reused from `.context-engineering/workspace_state.md` (you'll see them once and can change them)
        * dataset → `dataset/golden.json` is copied; the new experiment <"re-splits it as is (identical holdout, comparable verdicts)" | "expands it first, then splits">
        * seed context set → <`<Final Context Set resource>` | `vK/context_set_vK.json`>
        * first action → <one-line recommendation from the report>

        Start it with:
        "Start a new context-engineering experiment named `<experiment_name>-v2`, cloned from `<experiment_name>` for <"context fixes" | "dataset expansion">, seeded from its result, and apply the recommendations in `.context-engineering/experiments/<experiment_name>/hillclimb/final_evaluation_report.md`."
        ```
    *   The clone itself is performed by [context-engineering-init](../../context-engineering-init/SKILL.md) (clone mode) when the user issues that prompt — do **not** copy files or create the new experiment from this phase.

---

## Generalizability Diagnosis & Triage

When a user asks to act on a `final_evaluation_report.md` (typically with the hand-off prompt above), the agent inspects the final **Verdict** and routes remediation. **All remediation happens in the new, cloned experiment**: if the current experiment is the finished one (`## Final:` present in its `experiment_state.md`), first route to [context-engineering-init](../../context-engineering-init/SKILL.md) in clone mode (it copies `dataset/golden.json` only), then continue below inside the new experiment.

### 1. Verdict: INCONCLUSIVE
*   **Trigger:** The report indicates an INCONCLUSIVE verdict. This means the dataset is either too small or lacks the necessary variations to yield a statistically significant measure of generalizability.
*   **Dataset handling:** expand the copied `golden.json`, then split.
*   **Action:** Route to [context-engineering-dataset-generation](../../context-engineering-dataset-generation/SKILL.md) inside the new experiment, treating the copied `golden.json` as the user-supplied seed. Execute the expansion workflow to scale up the dataset using template-preserving strategies until it meets the required volume and variation thresholds, split with `split_dataset`, then run `context-engineering-hillclimb` seeded from the previous experiment's published context set.

### 2. Verdict: INVESTIGATE
When the verdict is INVESTIGATE, the model suffered a statistically significant generalization drop.

> [!IMPORTANT]
> **Anti-Data Leakage Rule:** You are STRICTLY FORBIDDEN from manually patching ContextSet Templates to memorize the specific `golden_sql` answers from the holdout set. You must resolve the root capability gaps, not the exact test answers, to prevent overfitting.

Read the report's actionable recommendations and route to the corresponding skill:
*   **Path A: Context & Metadata Deficiencies (Value Linking / Business Rule Gaps)**
    *   **Trigger:** Failures stem from a missing structural bridge between the user's intent and the database schema. This includes unmapped terminology, failure to link fuzzy search strings to strict database enums/IDs, or omitted table joins and filters.
    *   **Dataset handling:** split the copied `golden.json` **as is** (no expansion) — deterministic `split_dataset` reproduces the previous splits, so the verdicts stay comparable.
    *   **Action:** The dataset is fine; the gap is in the ContextSet's metadata. In the new experiment, let `context-engineering-dataset-generation` re-validate and split the copied `golden.json`, seed `v0` from the previous published context set, route to [context-engineering-generation-guide](../../context-engineering-generation-guide/SKILL.md) to author universally applicable `Value Searches` (for fuzzy logic) or parameterized `Facets` (for business filters) that bridge the missing logic, apply them to `v0/context_set_v0.json` via `mutate_context_set`, then run `context-engineering-hillclimb`.
*   **Path B: Curriculum Deficiencies (Phrasing Diversity Gaps)**
    *   **Trigger:** Failures stem from unseen concepts, colloquialisms, shorthand, or linguistic structures that the model was never exposed to within the training dataset.
    *   **Dataset handling:** expand the copied `golden.json`, then split.
    *   **Action:** Direct context patching is forbidden as it causes overfitting. In the new experiment, route to [context-engineering-dataset-generation](../../context-engineering-dataset-generation/SKILL.md) to execute the expansion workflow on the copied `golden.json`: generate new, diverse question/SQL pairs that teach the missing vocabulary, re-split (`dataset/splits/hillclimb.json` / `holdout.json`), then run `context-engineering-hillclimb` seeded from the previous published context set so the loop can learn the newly expanded curriculum.
