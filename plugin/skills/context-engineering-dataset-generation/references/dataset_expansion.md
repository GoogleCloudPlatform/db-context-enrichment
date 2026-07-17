# Dataset Expansion Workflow

> [!IMPORTANT]
> **Parent Skill Reference**: This phase operates as part of the workflow defined in `context-engineering-dataset-generation/SKILL.md`.

---

## 1. Prerequisite Verification
Before executing expansion candidates, verify:
1. **Approved Strategy Plan**: `evalset_gen_plan.md` exists and was explicitly approved. (`[GATE: USER-DECISION]`).
2. **Seed / Source Pairs**: The base pairs are available in the output dataset file.
3. **Database Execution Tools**: Check if `<source>-execute-sql` is available from `tools.yaml` for live query verification and Value Substitution (Strategy 6).

## 2. Expansion Execution
1. **Apply Expansion Strategies (`expansion-strategies.md`)**: Systematically apply the variation strategies and compound strategy combinations according to the exact budget allocation defined in `evalset_gen_plan.md`.
- **Respect the source domain:** Do not introduce NLQ topics not present in the source dataset without explicit user request.
- **Diversity over volume:** Avoid near-identical variants of the same pair. One strong, distinct variant beats three trivial ones.

2. **Example Candidate Tracking**: Track information for the candidates based on `dataset_format.md`.


