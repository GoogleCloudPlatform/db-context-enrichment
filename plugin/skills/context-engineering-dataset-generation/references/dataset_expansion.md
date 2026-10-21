# Dataset Expansion Workflow

> [!IMPORTANT]
> **Parent Skill Reference**: This phase operates as part of the workflow defined in `context-engineering-dataset-generation/SKILL.md`.

---

## 1. Prerequisite Verification
Before executing expansion candidates, verify:
1. **Approved Strategy Plan**: `evalset_gen_plan.md` exists and was explicitly approved. (`[GATE: USER-DECISION]`).
2. **Seed / Source Pairs**: The base pairs are available in `<dataset_dir>/temp_golden.json` (seeded from `<dataset_dir>/golden.json` when expanding a user-supplied or cloned dataset).
3. **Generalizability Report Recommendations (Cloned Experiments)**: If `experiment_state.md` records a `Source evaluation report` (`final_evaluation_report.md` from a prior experiment), verify that `evalset_gen_plan.md` and your planned expansion candidates directly address the report's `1. ACTIONABLE RECOMMENDATIONS` and `3. HOLDOUT SET FAILURE BREAKDOWN`. **Never append just 1 example per suggestion:** every suggested coverage pattern or phrasing category must be expanded into **at least 4–5 distinct template-preserving variations** (combining Paraphrasing, Distraction Injection, Linguistic Variation, and Value Substitution) so that `split_dataset` can distribute variations of each suggestion across **both** `splits/hillclimb.json` (~70% train) and `splits/holdout.json` (~30% test).
4. **Database Execution Tools**: Check if `<source>-execute-sql` is available from `tools.yaml` for live query verification and Value Substitution (Strategy 6).

## 2. Expansion Execution
1. **Apply Expansion Strategies (`expansion-strategies.md`)**: Systematically apply the variation strategies and compound strategy combinations according to the exact budget allocation defined in `evalset_gen_plan.md` (including full multi-variation expansion of every generalizability recommendation from a prior experiment's `final_evaluation_report.md` — at least 4–5 variations per suggested pattern, never single isolated items). Save the combined dataset (original seed pairs + new multi-variation groups) to `<dataset_dir>/temp_golden.json` via `generate_dataset` so Phase 6 can persist it to `<dataset_dir>/golden.json` **before** calling `split_dataset`.
- **Respect the source domain:** Do not introduce NLQ topics not present in the source dataset without explicit user request.
- **Diversity over volume:** Avoid near-identical variants of the same pair. One strong, distinct variant beats three trivial ones.

2. **Example Candidate Tracking**: Track information for the candidates based on `dataset_format.md`.


