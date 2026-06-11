---
name: autoctx-dataset-expansion
description: "Expands an existing NLQ/SQL evaluation dataset using six structural variation strategies: paraphrasing, merging, difficulty adjustment, distraction injection, linguistic variation, and value substitution. Can be invoked standalone or from within other skills (e.g., the Expansion phase of autoctx-dataset-generation)."
---

# Auto Context Generation - Dataset Expansion Workflow

This skill expands an existing NLQ/SQL evaluation dataset by applying targeted variation strategies to existing pairs. The goal is to increase dataset size, diversity, and robustness without requiring additional schema analysis or business context collection from scratch.

> [!IMPORTANT]
> **Prerequisite**: An existing source dataset (JSON file) in the [Standard Dataset Format](#standard-dataset-format) is required before this skill can operate. If no dataset exists yet, use the `autoctx-dataset-generation` skill first.

## Input

Before beginning the workflow, you explicitly require:

- **Source dataset path**: Absolute path to the existing `golden.json` (or equivalent) in the Standard Dataset Format.
- **Output file path**: Absolute path where expanded pairs should be written or appended. May be the same as the source file.
- **Active `tools.yaml`** (located in `autoctx/`): Required for value substitution (Phase 3, Strategy 6) and for SQL execution validation (Phase 4). If `tools.yaml` is not present, value substitution will be skipped and SQL execution validation will be degraded to syntax-only checking — warn the user.
- **Expansion strategies to apply** (ask the user): One or more of the six strategies listed below. Default to all six if the user has no preference.
- **Target pair count or multiplier**: Either a fixed number of new pairs to generate (e.g., "add 20 pairs") or a multiplier on the source dataset (e.g., "2x the dataset"). Default to generating at minimum 1 expansion per source pair if unspecified.

## Workflow

Follow these steps exactly in order:

---

### Phase 1: Input Validation & Batch State Initialization

1. **Read Source Dataset:**
   - Read the source dataset file. Verify it is valid JSON matching the Standard Dataset Format. If malformed, STOP and report the error to the user.
   - Count the total number of existing pairs and display a brief summary (pair count, distinct databases, complexity distribution from tags if present).

2. **Batch ID Initialization (Crucial):**
   - Scan the **output file** (if it already exists) for the highest existing `eval_<number>` ID.
   - Auto-increment this integer to establish the `<pair_id>` for the current invocation (e.g., if highest is `eval_012`, the next starts at `eval_013`).
   - If the output file does not exist or has no `eval_*` IDs, start at `eval_001`.
   - If the source file and output file are different, also check the source file and take the maximum across both.
   - Record the starting ID to ensure all pairs generated in this session use unique, sequential IDs.

3. **Tools Check:**
   - Check for `autoctx/tools.yaml`. If found, read it and identify the available database source(s).
   - If `tools.yaml` is missing or has no supported source, warn the user:
     > "No `tools.yaml` found. **Value Substitution** (Strategy 6) will be skipped and SQL execution validation will be limited to syntax checking only. To enable these features, run the `autoctx-init` skill first."
   - If multiple sources are available, list them and ask the user which database to use for execution and schema queries.

4. **Strategy & Target Confirmation:**
   - If the user has not already specified which strategies to apply, present the full list (see [Expansion Strategies](#expansion-strategies)) and ask for confirmation.
   - Confirm the total target number of new pairs.
   - Do NOT proceed to Phase 2 until the user has confirmed.

---

### Phase 2: Expansion Planning

Before generating any pairs, analyze the source dataset and produce a formal **Expansion Plan**.

The plan must cover:

1. **Source Dataset Analysis:**
   - Complexity distribution: how many pairs are tagged `low`, `medium`, `high` (or estimate if tags are absent).
   - Topic/domain coverage: which business themes appear.
   - SQL feature coverage: what SQL constructs are already present (simple SELECTs, JOINs, aggregations, CTEs, subqueries, window functions, etc.).
   - Pairs eligible for each strategy (e.g., only pairs with literal values in the NLQ are candidates for Value Substitution; only pairs that share related tables are candidates for Merging).

2. **Strategy Allocation:**
   - How many new pairs will each strategy contribute to reach the target count.
   - Which source pairs are assigned to which strategies (can be approximate at this stage).
   - Prioritize strategies that fill identified gaps (e.g., if the source dataset has no `high`-complexity pairs, prioritize Merging and Difficulty Upscaling).

3. **Target Complexity Distribution:**
   - Define the desired complexity distribution across all new pairs (e.g., 30% low, 40% medium, 30% high). Try to maintain or improve the distribution of the source dataset unless the user specifies otherwise.

4. **Value Substitution Column Targets:**
   - For pairs containing literal values, identify which column(s) to run `SELECT DISTINCT` on for candidate replacement values.

5. **Validation Criteria:**
   - All expanded SQL must be executable against the live database (if `tools.yaml` is available).
   - All expanded pairs must pass the **Blind Test** (another agent could reconstruct the SQL from only the NLQ and business context).
   - Pairs whose SQL returns 0 rows will be flagged but not automatically dropped — the user will decide.
   - Pairs failing execution will be dropped automatically.

> [!IMPORTANT]
> **Always present the Expansion Plan to the user for confirmation or edits before proceeding to Phase 3.** Save the approved plan to `./evalset_states/plans/eval_dataset_expansion_plan.md` (create the directory if needed).

---

### Phase 3: Expansion Execution

Apply each approved strategy using the source pairs identified in the plan. For every generated pair, execute the internal **Chain of Thought** described in each strategy below, then apply the [Cross-Strategy Validation Rules](#cross-strategy-validation-rules).

Use the following internal tracking format per generated candidate (not written to the output file — internal reasoning only):
- `source_id`: the `id` of the source pair(s)
- `strategy`: which strategy produced this candidate
- `status`: `pending_validation` | `approved` | `dropped`

---

#### Strategy 1: Paraphrasing

**Goal:** Reword the NLQ into a semantically equivalent question while keeping the SQL 100% unchanged.

**When to apply:** Any pair in the source dataset. Highly recommended for pairs with `complexity: low` or `complexity: medium` as they have simpler, more universally rephrashable NLQs.

**Execution steps:**
1. Read the source NLQ.
2. Generate 1–3 paraphrase variants that:
   - Change sentence structure (e.g., question → imperative, formal → informal, verbose → concise).
   - Replace business terms with synonyms where unambiguous (e.g., "accounts" → "customers", "retrieve" → "find").
   - Vary perspective (e.g., "How many X?" → "Give me the count of X" → "What is the total number of X?").
3. Do NOT change the `golden_sql`.
4. Apply the Blind Test: given only the new NLQ and the business domain, would the correct SQL be unambiguous? If a paraphrase loses precision (e.g., loses a key filter condition), discard it.
5. Tag: `"source: expansion:paraphrase"`.

**Example:**
- Source NLQ: `"How many accounts who choose issuance after transaction are staying in East Bohemia region?"`
- Paraphrase: `"Count the accounts in the East Bohemia region that opted for issuance after transaction."`
- SQL: *(unchanged)*

---

#### Strategy 2: Merging

**Goal:** Combine two or more source pairs into a single, more sophisticated NLQ/SQL pair using subqueries, CTEs, or multi-condition logic.

**When to apply:** Source pairs that share at least one common table or concept. Do NOT merge pairs from different databases.

**Execution steps:**
1. Identify 2–3 source pairs that are logically composable (e.g., one filters accounts by region, another filters by loan eligibility).
2. Draft the merged SQL first (schema-first approach):
   - Use a CTE, subquery, or compound WHERE clause to represent the combined logic.
   - Verify all table references and join conditions are valid against the schema.
   - Run the merged SQL via `<source>-execute-sql` to confirm it is executable.
3. Translate the merged SQL to a literal English description, then humanize it following the Semantic Bridge principle.
4. Apply the Blind Test.
5. Set `complexity` tag to at least one level higher than the highest-complexity source pair.
6. Tag: `"source: expansion:merge"`, `"expansion_source_ids: [eval_001, eval_002]"`.

**Example:**
- Source 1: "How many accounts are in Prague?" → `SELECT count(*) FROM account JOIN district ON ... WHERE A3 = 'Prague'`
- Source 2: "Which accounts have loans?" → `SELECT account_id FROM loan`
- Merged NLQ: `"How many accounts located in Prague are also eligible for loans?"`
- Merged SQL: `SELECT COUNT(DISTINCT a.account_id) FROM account a JOIN district d ON a.district_id = d.district_id JOIN loan l ON a.account_id = l.account_id WHERE d.A3 = 'Prague'`

---

#### Strategy 3: Difficulty Adjustment

**Goal:** Create a simpler or more sophisticated variant of a single source pair by adding or removing SQL constructs.

**When to apply:**
- **Downscaling**: Source pairs with `complexity: medium` or `complexity: high`.
- **Upscaling**: Source pairs with `complexity: low` or `complexity: medium`.

**Execution steps — Downscaling (Simplification):**
1. Identify a complex construct to remove: a JOIN, aggregation, subquery, window function, or a specific WHERE clause condition.
2. Rewrite the SQL with the construct removed, ensuring the result is still a valid, meaningful query.
3. Adjust the NLQ to accurately reflect the simplified question (dropping the nuance that was removed).
4. Reduce the `complexity` tag accordingly.
5. Tag: `"source: expansion:simplify"`.

**Execution steps — Upscaling (Sophistication):**
1. Identify an opportunity to add a meaningful construct: add a `GROUP BY` + aggregation, convert a flat query to a CTE, add a `HAVING` clause, add a ranking window function (`ROW_NUMBER`, `RANK`), add an additional JOIN to another related table, or add a date/range filter.
2. Draft the enriched SQL (schema-first). Confirm all new column/table references exist in the schema.
3. Run via `<source>-execute-sql` to confirm executability.
4. Update the NLQ to accurately reflect the added complexity.
5. Increase the `complexity` tag accordingly.
6. Tag: `"source: expansion:upscale"`.

---

#### Strategy 4: Distraction Injection

**Goal:** Add misleading or irrelevant information to the NLQ that does NOT change the SQL. This tests whether the Data Agent can filter noise from user questions.

**When to apply:** Any pair, but prefer pairs with `complexity: low` or `complexity: medium` where the added noise is clearly extraneous.

**Distraction types:**
- **Irrelevant entity mention**: Mention a table or concept that is not part of the SQL (e.g., "I looked at the transactions table but I actually want to know...").
- **Redundant condition**: Add a condition that is always true or subsumed by an existing condition (e.g., "...where the account exists AND is in Prague" when the Prague filter already implies existence).
- **Out-of-scope qualifier**: Add a time-based or status-based qualifier that sounds meaningful but maps to no column (e.g., "as of today", "currently active" when there is no status column). Only use this if the schema genuinely lacks such a column — do not invent filters.
- **Conversational filler**: Add preamble like "I was wondering...", "Can you help me find...", or "For a report I'm building...".

**Execution steps:**
1. Choose one distraction type appropriate to the pair.
2. Inject the distraction into the NLQ only. The `golden_sql` must remain bit-for-bit identical.
3. Apply the Blind Test with extra scrutiny: confirm that the distraction does NOT cause ambiguity about which SQL should be produced.
4. Tag: `"source: expansion:distraction"`.

---

#### Strategy 5: Linguistic Variation

**Goal:** Introduce realistic linguistic noise — typos, synonyms, domain acronyms — that a real user might type. This tests robustness to imperfect natural language input.

**When to apply:** Any pair. Apply sparingly — 1–2 variants per source pair maximum. Do NOT apply linguistic variation to already-distraction-injected variants of the same pair.

**Variation types (apply one or two per variant, not all at once):**

- **Typos**: Introduce 1–2 plausible typing errors in the NLQ (e.g., "acocunts" for "accounts", "hwo many" for "how many"). Do NOT introduce typos in values that map directly to SQL literals (e.g., don't typo `'POPLATEK PO OBRATU'` if it appears in the NLQ, as that would make the Blind Test ambiguous).
- **Synonyms**: Replace business terms with synonyms (e.g., "clients" → "customers", "loan" → "credit", "region" → "area", "eligible" → "qualified").
- **Acronyms**: Replace spelled-out terms with domain acronyms where plausible (e.g., "natural language query" → "NLQ", "year to date" → "YTD", "month over month" → "MoM").
- **Informal phrasing**: Use colloquial contractions or casual phrasing (e.g., "what's" instead of "what is", "gimme" instead of "give me", "show me" instead of "retrieve").

**Execution steps:**
1. Select 1–2 variation types from the list above.
2. Apply them to the NLQ. The `golden_sql` must remain unchanged.
3. Apply the Blind Test: despite the noise, would a skilled agent still produce the correct SQL? If the variation makes the question too ambiguous, discard it.
4. Tag: `"source: expansion:linguistic"`.

---

#### Strategy 6: Value Substitution

**Goal:** Replace a literal value mentioned in the NLQ (and its corresponding SQL literal) with a different real value from the same column. This generates semantically identical pairs with different parameters, improving value-coverage in the dataset.

**When to apply:** Pairs that contain at least one literal string or numeric value in both the NLQ and the SQL WHERE clause (e.g., `WHERE district.A3 = 'Prague'` with "Prague" also appearing in the NLQ).

> [!IMPORTANT]
> This strategy **requires** an active `tools.yaml` and a live database connection. If unavailable, skip this strategy entirely and notify the user.

**Execution steps:**
1. Identify the literal value(s) in the NLQ that map directly to a SQL WHERE clause literal.
2. For each identified value, determine its source table and column (e.g., `district.A3 = 'Prague'` → table `district`, column `A3`).
3. **Run value discovery query:**
   ```sql
   SELECT DISTINCT "<column>" FROM "<table>" WHERE "<column>" IS NOT NULL ORDER BY 1 LIMIT 20;
   ```
   Execute this via `<source>-execute-sql`.
4. Remove the source value from the candidate list. Select 1–3 alternative values.
5. For each alternative value:
   a. Replace the literal in the `golden_sql` WHERE clause.
   b. Replace the corresponding term in the NLQ (use the exact value or a natural equivalent).
   c. Run the substituted SQL via `<source>-execute-sql` to confirm it executes and returns rows.
   d. If it returns 0 rows, flag with `"result: empty_result"` tag and ask the user whether to include or drop it.
   e. Apply the Blind Test.
6. Tag: `"source: expansion:value_substitution"`, `"substituted_column: <table>.<column>"`.

**Example:**
- Source NLQ: `"How many accounts in Prague are eligible for loans?"`
- Source SQL: `...WHERE district.A3 = 'Prague'`
- Value discovery: `SELECT DISTINCT "A3" FROM "district" ORDER BY 1 LIMIT 20` → returns `['Prague', 'south Bohemia', 'east Bohemia', 'north Moravia', ...]`
- Substituted pair: `"How many accounts in south Bohemia are eligible for loans?"` with SQL: `...WHERE district.A3 = 'south Bohemia'`

---

### Cross-Strategy Validation Rules

Apply these rules to every candidate pair, regardless of strategy, before marking it `approved`:

1. **SQL Execution (if `tools.yaml` available):**
   - Execute the `golden_sql` via `<source>-execute-sql`.
   - If execution throws an error → mark `dropped`. Log the error in the validation report.
   - If execution returns 0 rows → mark `flagged:empty_result`. Do NOT auto-drop. Report to user and wait for instruction.
   - If execution returns rows → mark `approved` (subject to Blind Test below).

2. **Blind Test:**
   - Look only at the new NLQ (and the database name/domain). Could another agent unambiguously produce the exact `golden_sql`?
   - If the NLQ is too vague, ambiguous, or inconsistent with the SQL → refine the NLQ or mark `dropped`.

3. **Schema Fidelity:**
   - No invented table names or column names in `golden_sql`.
   - All column references exist in the schema (cross-check if schema was fetched in Phase 1).

4. **No Duplication:**
   - Check the output file for near-identical NLQs. Do not add pairs that are trivially identical to an already-existing pair.

5. **Semantic Bridge:**
   - The NLQ must use business vocabulary, not raw SQL column/table names (e.g., NLQ should say "region" not `A3`, "issuance frequency" not `frequency`). Exception: if the column name is itself a natural business term.

---

### Phase 4: Validation Report

After all candidates have been processed through Cross-Strategy Validation, generate a two-tier validation report.

> [!IMPORTANT]
> **Present the validation report plan to the user for confirmation before writing the reports.** Save the approved review plan to `./evalset_states/plans/eval_dataset_expansion_review_plan.md`.

**Tier 1 — Pair-Level Review:**

For every candidate pair (approved, dropped, and flagged), produce a structured entry:

```markdown
### Pair: <new_id> (from <source_id> via <strategy>)
- **Status**: Approved | Dropped | Flagged:empty_result
- **NLQ**: "<the NLQ>"
- **SQL**: `<the golden_sql>`
- **Execution Result**: Returned N rows | Error: <message> | 0 rows (flagged)
- **Blind Test**: Pass | Fail — <reason if fail>
- **Drop/Flag Reason**: <if applicable>
- **Complexity**: low | medium | high
- **Topic**: <business domain>
```

Save to `./evalset_states/reports/eval-dataset-expansion-review-pair-level.md`.

**Tier 2 — Dataset-Level Summary:**

Aggregate across all approved pairs:

```markdown
# Dataset Expansion Summary

## Source Dataset
- Total source pairs: N
- Databases: [list]

## Expansion Results
| Strategy             | Candidates | Approved | Dropped | Flagged (0 rows) |
|----------------------|------------|----------|---------|-----------------|
| Paraphrase           | X          | X        | X       | X               |
| Merge                | X          | X        | X       | X               |
| Difficulty Adjust    | X          | X        | X       | X               |
| Distraction          | X          | X        | X       | X               |
| Linguistic Variation | X          | X        | X       | X               |
| Value Substitution   | X          | X        | X       | X               |
| **Total**            | **X**      | **X**    | **X**   | **X**           |

## Complexity Distribution (Approved Pairs)
- Low: X (X%)
- Medium: X (X%)
- High: X (X%)

## SQL Feature Coverage (Approved Pairs)
- Simple SELECT: X
- Aggregation (COUNT, SUM, AVG): X
- JOINs: X
- GROUP BY / HAVING: X
- Subqueries / CTEs: X
- Window Functions: X

## Topics Covered
<list of distinct topic tags>
```

Save to `./evalset_states/reports/eval-dataset-expansion-review-dataset-level.md`.

Present both reports to the user. Wait for their confirmation (and any manual overrides for flagged pairs) before writing to the output file.

---

### Phase 5: Output

1. **Apply User Overrides:** If the user manually approved any `flagged:empty_result` pairs or restored any dropped pairs, update their status to `approved`.

2. **Write Approved Pairs:** Use the `generate_dataset` MCP tool to append all `approved` pairs to the output file path. Always use the **absolute path**. Pairs must conform to the Standard Dataset Format.

3. **Assign Tags:** Every expanded pair must include:
   - `"complexity: <low|medium|high>"`
   - `"topic: <business_domain>"`
   - `"source: expansion:<strategy_name>"` (e.g., `"source: expansion:paraphrase"`)
   - `"expansion_source_id: <source_pair_id>"` (for single-source strategies)
   - `"expansion_source_ids: [<id1>, <id2>]"` (for Merge strategy only)
   - Where applicable: `"substituted_column: <table>.<column>"` (Value Substitution only)

4. **Final Summary:** Report to the user:
   - Total approved pairs written.
   - Breakdown by strategy.
   - Final combined dataset size (original + new).
   - Exact output file path.
   - Suggest next step: run evaluation using the `autoctx-evaluate` skill on the expanded dataset.

---

## Standard Dataset Format

All input and output files must use this JSON schema:

```json
[
    {
        "id": "eval_001",
        "database": "<database_name>",
        "nlq": "How many accounts in Prague are eligible for loans?",
        "golden_sql": "SELECT COUNT(DISTINCT a.account_id) FROM account a JOIN district d ON a.district_id = d.district_id JOIN loan l ON a.account_id = l.account_id WHERE d.A3 = 'Prague'",
        "tags": [
            "complexity: medium",
            "topic: loan_eligibility",
            "source: expansion:value_substitution",
            "expansion_source_id: eval_002",
            "substituted_column: district.A3"
        ]
    }
]
```

- **`complexity`**: `"low"` (single table, no aggregation), `"medium"` (multi-table JOIN or aggregation), `"high"` (CTEs, subqueries, window functions, multi-condition logic).
- **`topic`**: Business domain or analytical theme (e.g., `"loan_eligibility"`, `"account_activity"`, `"regional_distribution"`).
- **`source`**: Must include the prefix `"expansion:"` followed by the strategy name for all pairs generated by this skill.
- **`expansion_source_id`** / **`expansion_source_ids`**: Traceability back to the original pair(s).

## Interaction Guidelines

- **Confirm at every gate:** This skill has two mandatory user confirmation gates — after presenting the Expansion Plan (Phase 2) and after presenting the Validation Reports (Phase 4). Do not skip these.
- **Be transparent about drops:** Always report exactly why a candidate was dropped — SQL execution error, Blind Test failure, or schema violation.
- **Batch efficiently:** When running SQL execution for validation, batch `<source>-execute-sql` calls efficiently rather than one at a time where the tooling supports it.
- **Respect the source dataset's domain:** Do not generate NLQs that venture into business domains not reflected in the source dataset unless the user explicitly requests broadening the scope.
- **Do not over-expand:** Avoid creating so many near-identical variants of a single pair that the dataset becomes repetitive. Aim for diversity first.
