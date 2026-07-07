# Dataset Expansion Strategies

This document defines the six expansion strategies used by the `autoctx-dataset-expansion` skill. For every generated pair, use the Chain of Thought below regardless of strategy, then apply the **Validation Gate** defined in the main skill.

## Chain of Thought (All Strategies)

For every candidate:
1. **Draft SQL (Schema-First):** Write syntactically correct, dialect-compliant SQL. Use only columns and tables confirmed in the schema. Ensure any `LIMIT` or window function includes a tie-breaking `ORDER BY`.
2. **Literal Translation:** Translate the SQL literally into English to surface all logical constraints.
3. **Humanize & Bridge:** Rewrite into natural business language. Never leak raw column names into the NLQ.
4. **Blind Test:** Looking only at the NLQ and business context — could another agent produce the exact SQL? If ambiguous, refine or discard.

---

## Strategy 1: Paraphrasing

**Goal:** Reword the NLQ into a semantically equivalent question while keeping the `golden_sql` 100% unchanged.

**When to apply:** Any pair. Especially effective for `complexity: low` or `complexity: medium` pairs where the NLQ is straightforwardly rephraseable.

**Execution:**
1. Generate 1–3 NLQ variants that:
   - Change sentence structure (question → imperative, formal → informal, verbose → concise).
   - Replace business terms with unambiguous synonyms (e.g., "accounts" → "customers").
   - Vary perspective ("How many X?" → "Give me the count of X" → "What is the total number of X?").
2. Do NOT change `golden_sql`.
3. Apply the Blind Test. Discard any variant that loses precision (drops a key filter condition).
4. Tag: `"source: expansion:paraphrase"`.

**Anti-pattern:** Do not create a paraphrase so vague that it could map to a different SQL (e.g., dropping the region filter from a region-specific question).

---

## Strategy 2: Merging

**Goal:** Combine two or more source pairs into a single, more sophisticated NLQ/SQL pair using subqueries, CTEs, or compound conditions.

**When to apply:** Source pairs that share at least one common table or concept. Do NOT merge pairs from different databases.

**Execution:**
1. Identify 2–3 logically composable source pairs.
2. Draft the merged SQL first (schema-first):
   - Use a CTE, subquery, or compound WHERE clause.
   - Verify all table references and join conditions.
3. Humanize the merged SQL into a natural NLQ following the Semantic Bridge principle.
4. Apply the Blind Test.
5. Set `complexity` tag to at least one level higher than the highest-complexity source pair.
6. Tags: `"source: expansion:merge"`, `"expansion_source_ids: [eval_001, eval_002]"`.

**Anti-pattern:** Do not build "Frankenstein" queries with 5+ joins unless explicitly asked for a `complexity: high` pair.

---

## Strategy 3: Difficulty Adjustment

**Goal:** Create a simpler or more sophisticated variant by adding or removing SQL constructs.

**When to apply:**
- **Simplification (Downscale):** Source pairs with `complexity: medium` or `complexity: high`.
- **Sophistication (Upscale):** Source pairs with `complexity: low` or `complexity: medium`.

**Execution — Simplification:**
1. Remove one construct: a JOIN, aggregation, subquery, window function, or a specific WHERE condition.
2. Rewrite the SQL with the construct removed (result must still be valid and meaningful).
3. Adjust the NLQ to accurately reflect the simplified question.
4. Reduce the `complexity` tag accordingly.
5. Tag: `"source: expansion:simplify"`.

**Execution — Sophistication (Upscaling):**
1. Add a meaningful construct: `GROUP BY` + aggregation, CTE conversion, `HAVING` clause, ranking window function (`ROW_NUMBER`, `RANK`), additional JOIN to a related table, or a date/range filter.
2. Draft the enriched SQL (schema-first). Confirm all new column/table references exist.
3. Update the NLQ to accurately reflect the added complexity.
4. Increase the `complexity` tag accordingly.
5. Tag: `"source: expansion:upscale"`.

**Anti-pattern (Upscaling):** Do not add complexity for its own sake. The added construct must serve a realistic business question.

---

## Strategy 4: Distraction Injection

**Goal:** Add misleading or irrelevant information to the NLQ that does NOT change the SQL. Tests whether the Data Agent can filter noise.

**When to apply:** Any pair. Prefer `complexity: low` or `complexity: medium` where the noise is clearly extraneous.

**Distraction types (choose one per variant):**
- **Irrelevant entity mention:** Reference a table/concept not part of the SQL (e.g., "I looked at the transactions table but what I need is...").
- **Redundant condition:** Add a condition always true or subsumed by an existing filter.
- **Out-of-scope qualifier:** Add a time/status qualifier that sounds meaningful but maps to no schema column (only use if the column genuinely does not exist — never invent filters).
- **Conversational filler:** Add preamble like "I was wondering...", "For a report I'm building...", "Can you help me find...".

**Execution:**
1. Choose one distraction type.
2. Inject into the NLQ only. `golden_sql` must be bit-for-bit identical.
3. Apply the Blind Test with extra scrutiny: the distraction must NOT cause ambiguity about which SQL to produce.
4. Tag: `"source: expansion:distraction"`.

---

## Strategy 5: Linguistic Variation

**Goal:** Introduce realistic linguistic noise — typos, synonyms, acronyms, informal phrasing — that a real user might type.

**When to apply:** Any pair. Apply sparingly — maximum 1–2 variants per source pair. Do NOT combine with Distraction on the same pair.

**Variation types (apply one or two per variant):**
- **Typos:** 1–2 plausible typing errors (e.g., `"acocunts"`, `"hwo many"`). Do NOT typo values that map to SQL literals, as this makes the Blind Test ambiguous.
- **Synonyms:** Replace business terms (e.g., "clients" → "customers", "loan" → "credit", "region" → "area").
- **Acronyms:** Use domain acronyms where plausible (e.g., "year to date" → "YTD", "month over month" → "MoM").
- **Informal phrasing:** Contractions or casual language (e.g., "what's" instead of "what is", "show me" instead of "retrieve").

**Execution:**
1. Apply chosen variation(s) to the NLQ. `golden_sql` must be unchanged.
2. Apply the Blind Test: despite the noise, would a skilled agent produce the correct SQL?
3. Tag: `"source: expansion:linguistic"`.

---

## Strategy 6: Value Substitution

**Goal:** Replace a literal value in the NLQ and its corresponding SQL WHERE clause with a different real value from the same column. Generates structurally identical pairs with different parameters.

**When to apply:** Pairs that contain a literal string or numeric value in both the NLQ and the SQL WHERE clause. Requires a live database connection (`tools.yaml`). If unavailable, skip this strategy.

**Execution:**
1. Identify the literal value(s) in the NLQ that map to SQL WHERE clause literals.
2. Determine the source table and column (e.g., `district.A3 = 'Prague'` → table `district`, column `A3`).
3. **Run value discovery:**
   ```sql
   SELECT DISTINCT "<column>" FROM "<table>" WHERE "<column>" IS NOT NULL ORDER BY 1 LIMIT 20;
   ```
4. Remove the source value from the candidate list. Select 1–3 alternatives.
5. For each alternative:
   - Replace the literal in `golden_sql`.
   - Replace the term in the NLQ (use the actual value or a natural equivalent).
   - Run the substituted SQL via `<source>-execute-sql`.
   - 0 rows → flag with `"result: empty_result"`.
   - Apply the Blind Test.
6. Tags: `"source: expansion:value_substitution"`, `"substituted_column: <table>.<column>"`.

**Anti-pattern:** Do not count changing `region = 'East'` to `region = 'West'` without also verifying the new value actually exists in the database and the query returns rows.
