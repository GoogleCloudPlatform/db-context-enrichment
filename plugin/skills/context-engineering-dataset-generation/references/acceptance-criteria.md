# Acceptance Criteria & Operational Validation Gate

## Operational Validation Gate

For *every* candidate pair - irrespective of the source - execute the following mandatory step-by-step validation protocol before saving a pair to file. 

- Batch validation of all examples by steps: going through step 1, then step 2, etc.
- If backtracking as part of fixing a query or refining a question, track the query as part of a set to be fixed, and then batch backtracking together. 
- Do **not** skip any step. Do **not** proceed to the next step until the current step is successfully completed.

### Step 1: Format and Logical Requirements Validation
1. Check adherence to format in dataset_format.md

### Step 2: Example Logical Requirement Validation

1. Strict Schema Fidelity (Zero Hallucination)
* **Rule:** The SQL must exclusively use the tables, columns, data types, and relationships explicitly confirmed in the target database schema (`<source>-list-schemas`).
* **Enforcement:** Do not invent missing columns, guess foreign key relationships, or assume undocumented system columns (`created_at`, `is_deleted`, `status`) exist.

2. The "Blind" Reversibility Test & Semantic Bridge
* **Rule:** The natural language question (NLQ) and business context must contain sufficient information for another agent or human SME to deterministically deduce the exact `golden_sql` logic without seeing the query (`Blind Test`).
* **Enforcement:** Evaluate blindly. If key filters, groupings, or join conditions are ambiguous or missing from the NLQ, refine the question or drop the pair.
* **Semantic Bridge:** The NLQ must remain conversational and use natural business phrasing. Never leak raw column names, table aliases (`t1`), or dictated SQL structure into English (e.g. avoid "Select column A from table B where...").

3. Deterministic Output (Robust Ordering)
* **Rule:** The SQL query must yield consistently reproducible results across runs, independent of the database engine's default sorting behavior.
* **Enforcement:** Any query utilizing limits, rankings, or window functions (`LIMIT`, `ROW_NUMBER()`, `RANK()`, `TOP`) **must** include an explicit `ORDER BY` clause with a unique tie-breaker column (`account_id`, `id`).

4. Business Realism & Logical Coherence
* **Rule:** The NLQ must represent a plausible, real-world analytical question that a business user would actually ask.
* **Enforcement:** Reject queries that perform mathematically invalid or meaningless operations (e.g., averaging phone numbers, summing categorical IDs, or joining unrelated tables solely to increase complexity).

5. Modern SQL Best Practices & Structure
* **Rule:** The SQL must follow clean, readable engineering standards.
* **Enforcement:**
  * Use explicit `JOIN ... ON` syntax instead of implicit, comma-separated `FROM` clauses.
  * Use clear table aliases (`t1`, `t2` or meaningful short abbreviations like `u` for `users`).
  * Never write `SELECT *`. Always specify exact, explicit columns.

### Step 3: Execution-Guided Verification (`<source>-execute-sql`)
1. **Execute the Query:** Run `golden_sql` against the active database configuration identified from `tools.yaml`. Batch SQL calls **efficiently** rather than one at a time.
2. **Handle Syntax & Schema Errors:** If execution fails due to syntax error, unknown column/table, or type mismatch, immediately refine the query and re-verify. If unfixable, mark as `dropped` and log the exact error. Always state why a candidate was dropped — execution error, Blind Test failure, schema violation, etc.
3. **Handle Empty Results (0 Rows Returned):**
   - If the query executes without errors but returns 0 rows, check whether it stems from a logically impossible condition (`WHERE x = 1 AND x = 2`). If so, fix or drop.
   - If the query represents a realistic filter (`WHERE region = 'Antarctica'`) that currently matches 0 records, mark the candidate with tag `"flagged:empty_result"`. Do NOT automatically drop realistic 0-row queries. We batch them for HITL review later.
4. **Validation Log Rule:** For every successfully verified query, state in your reasoning: *"Verified eval_XXX against [Source Name]."*

### Step 4: Uniqueness & Deduplication Check
1. Verify the candidate is not trivially identical or semantically duplicate to any existing pair already written in the target output file (`golden.json`). If a duplicate exists, drop the candidate.

