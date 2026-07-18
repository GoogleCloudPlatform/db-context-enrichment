# NL2SQL Dataset Audit & Review Protocol

> [!IMPORTANT]
> **Parent Skill Reference**: This reference is used as part of the `AUDIT & REPORTING [GATE: USER_APPROVAL]` workflow defined in `context-engineering-dataset-generation/SKILL.md`. Do not execute these steps without adhering to `SKILL.md`.

This protocol dictates the strict evaluation standards, file persistence management, and structured reporting formats for the evaluated NL-SQL pairs. The audit is broken into two distinct tiers: **Individual Pair-Level Review (`Report 1`)** and **Aggregate Dataset-Level Reporting (`Report 2`)**.

---

## Goal & File Management
You must generate and maintain two final markdown reports (`evalset_report_pair_level.md` and `evalset_report_dataset_level.md`). Pay strict attention to file persistence: 
* **If file already exists:** Read the existing files and intelligently append or update the metrics without destroying historical data or user-approved notes.
* **If file does not exist:** Create the files.

---

## Report 1: `evalset_report_pair_level.md` (Pair-Level Audit)

Evaluate every candidate evaluation example (`eval_XXX` whether user-provided, generated during seed creation, or created via variation expansion) against the criteria below, and output a structured table containing every finalized pair.

### Audit Criteria per Pair
1. **Context Utilization & Grounding:** Does the pair rely specifically on the provided business domain, or is it generic? Cite the exact grounding source (`evalset_environment_inputs.md`, local file, DB schema snippet, or parent seed ID).
2. **NLQ Quality (Realism & Ambiguity):** Is the English question conversational and realistic for a business user? Does it follow the *Semantic Bridge* principle (no raw column leakage)?
3. **SQL Correctness & Equivalence:** Is the SQL syntactically sound and verified via `<source>-execute-sql`? Does it strictly adhere to `acceptance-criteria.md` (no hallucinated schema, explicit `ORDER BY` tie-breakers)?
4. **Complexity Categorization:** Tag the SQL execution complexity as **Low/Simple** (basic SELECT/WHERE), **Medium** (JOINs, basic aggregations, GROUP BY), or **High/Complex** (CTEs, Window Functions, Subqueries, layered conditions).
5. **Source Attribution:** Verify exact origin tagging per `dataset_format.md`: (`"source: user_provided:file.json"`, `"source: generated:schema+code"`, or `"source: expansion:strategy_name"`). If multiple expansion strategies were combined on a single pair, list all applied strategies (e.g., `"source: expansion:value_substitution+upscale"`).

### Required Structured Format for Report 1
You must format `evalset_report_pair_level.md` using clean summary tables applicable to both generated and expanded examples:

```markdown
# Pair-Level Evaluation Audit Report (`evalset_report_pair_level.md`)

| ID | Status | Complexity | Origin / Strategy Tag | Grounding Citation | Quality / Correctness Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eval_001` | Approved | Medium | `user_provided:input.json` | `Sales Report (p. 4)` | Verified execution against AlloyDB; explicit JOINs and unique tie-breaker ordering confirmed. |
| `eval_002` | Approved | Low | `generated:schema+code` | `district.A3` | Validated single-table filter on Prague region during seed generation. |
| `eval_003` | Flagged | High | `expansion:value_substitution` | `district.A3` | Executed without syntax errors, but currently returns 0 rows (`flagged:empty_result`). |
| `eval_004` | Dropped | Medium | `expansion:merge` | `account + loan` | Dropped due to blind reversibility test failure (ambiguous join intent in NLQ). |
| `eval_005` | Approved | High | `expansion:value_substitution+upscale+linguistic` | `district.A3 + loan` | Combined strategy derivation: substituted `A3`, added `loan` JOIN, and introduced domain acronym `YTD`. |
```

* **Constraint:** If pair-level audit reveals unfixable errors or schema violations, mark them `Dropped` and state why. If an error can be remediated (e.g., missing tie-breaking `ORDER BY`), you **must** backtrack and fix the query before finalizing the report.

---

## Report 2: `evalset_report_dataset_level.md` (User-Reviewed Executive Summary)

Use the pair-level audit findings to generate the dataset-level aggregate report. **This report serves as the primary executive artifact presented to the user during the review touchpoint gate.**

### Aggregate Dimensions
1. **Schema Heatmap:** Analyze which tables and columns are queried most frequently across both generated and expanded examples. Identify critical schema elements that were neglected.
2. **Complexity Distribution:** Calculate absolute counts and percentage breakdown of Low vs. Medium vs. High queries across the entire dataset.
3. **SQL Taxonomy Coverage:** List absolute counts and frequencies of specific SQL features across all examples (`% using CTEs`, `% using explicit JOINs`, `% using Window functions`, `% using Date/Time functions`).
4. **Analytical Intent Diversity:** Categorize the types of business questions asked into functional archetypes (Operational lookups, Aggregation/Summary, Ranking/Top-N, Temporal comparisons) with absolute counts and percentages.
5. **Two-Table Origin & Strategy Breakdown:** 
   - **Table 2A (Source Composition):** Mutually exclusive breakdown across user seeds, generated seeds, and expanded pairs (`summing to 100%`).
   - **Table 2B (Expansion Strategy Breakdown):** Non-mutually exclusive breakdown of applied variation strategies (`not summing to 100% since multiple strategies can apply to a single example`).

### Required Structured Format for Report 2
You must format `evalset_report_dataset_level.md` using the exact structure below so that it applies uniformly whether the dataset contains generated examples, expanded examples, or both:

```markdown
# Dataset-Level Evaluation Audit & Executive Summary (`evalset_report_dataset_level.md`)

## 1. Executive Summary & Source Inventory
- **Target Database / Dialect**: `<database_name> (<dialect>)`
- **User-Provided Input Seeds**: `N pairs` (`user_provided:*`)
- **Newly Generated Seeds**: `N pairs` (`generated:*`)
- **Augmented / Expanded Pairs**: `N pairs` (`expansion:*`)
- **Total Combined Dataset Volume**: `N approved pairs` (plus `N flagged:empty_result` awaiting review)

---

## 2. Dataset Generation & Expansion Summary Tables

### Table 2A: Overall Dataset Source Composition
*(Note: Every approved pair belongs to exactly one primary origin. Absolute counts and percentages below sum to 100% of the total approved dataset.)*

| Primary Origin | Candidates Evaluated | Approved & Kept | Dropped (Error/Fail) | Flagged (`0 rows`) | % of Final Dataset (`N=Total`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **User-Provided Seeds (`user_provided:*`)** | X | X | X | X | X% (`Count / Total`) |
| **Seed Generation (`generated:*`)** | X | X | X | X | X% (`Count / Total`) |
| **Augmented / Expanded (`expansion:*`)** | X | X | X | X | X% (`Count / Total`) |
| **TOTALS** | **X** | **X** | **X** | **X** | **100%** |

### Table 2B: Expansion Strategy Breakdown
*(Note: Because multiple expansion strategies can be combined across a single example's derivation lineage—e.g. applying Value Substitution along with Upscaling and Linguistic Variation—the applied strategy counts and percentages below are non-mutually exclusive and will not sum to 100%.)*

| Expansion Strategy | Candidates Evaluated | Approved & Kept | Dropped (Error/Fail) | Flagged (`0 rows`) | % of Expanded Pairs (`N=Expanded`) | % of Total Dataset (`N=Total`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Paraphrasing (`Strategy 1`)** | X | X | X | X | X% | X% |
| **Merging (`Strategy 2`)** | X | X | X | X | X% | X% |
| **Difficulty Adjust (`Strategy 3`)** | X | X | X | X | X% | X% |
| **Distraction Injection (`Strategy 4`)** | X | X | X | X | X% | X% |
| **Linguistic Variation (`Strategy 5`)** | X | X | X | X | X% | X% |
| **Value Substitution (`Strategy 6`)** | X | X | X | X | X% | X% |

---

## 3. Complexity & Analytical Intent Distribution
- **Complexity Breakdown (Absolute Counts & % of Total Dataset)**:
  - `Low / Simple` (Single table, basic SELECT/WHERE): `N pairs (X%)`
  - `Medium` (Multi-table JOINs, basic GROUP BY / aggregations): `N pairs (X%)`
  - `High / Complex` (CTEs, Window Functions, Subqueries, multi-condition logic): `N pairs (X%)`

- **Analytical Intent Taxonomy (Absolute Counts & % of Total Dataset)**:
  - `Operational Lookups` (Point lookups, single-record retrieval, existence checks): `N pairs (X%)`
  - `Aggregation & Summary` (Summing, averaging, counting across groupings): `N pairs (X%)`
  - `Ranking & Top-N Analysis` (Ordering, LIMITs, top/bottom performers): `N pairs (X%)`
  - `Temporal / Trend Comparisons` (Date range bounding, year-over-year, month-over-month): `N pairs (X%)`

---

## 4. Schema Heatmap & SQL Feature Taxonomy Coverage
- **Top Queried Tables/Columns**: `table1 (X%)`, `table2.col (X%)`, `table3 (X%)`.
- **SQL Feature Inventory (Absolute Counts & % of Total Dataset)**:
  - `Explicit JOINs`: X% (`N pairs`)
  - `Aggregations / GROUP BY / HAVING`: X% (`N pairs`)
  - `CTEs / Subqueries`: X% (`N pairs`)
  - `Window Functions / Rankings (`ORDER BY`)`: X% (`N pairs`)

---

## 5. Gap Analysis & Next Target Recommendations
- **Identified Schema Gaps**: `<List any key tables, columns, or relationships not yet covered>`
- **Recommended Next Steps**: `<Provide concrete recommendations for future hill-climbing tuning or expansion>`

---

## 6. Action Required: `flagged:empty_result` User Review Gate
> [!IMPORTANT]
> **Keep vs. Replace Decision**: We have `N pairs` (`eval_XXX`, `eval_YYY`) that executed cleanly without syntax errors against `<source>-execute-sql` but returned `0 rows`.
> **Please review and reply:**
> - Reply **"KEEP ALL"** (or specify IDs) to confirm them as valid 0-row test cases in the final dataset (`golden.json`).
> - Reply **"REPLACE ALL"** (or specify IDs) to backtrack and generate replacement queries with non-zero parameter values before finalization.
```