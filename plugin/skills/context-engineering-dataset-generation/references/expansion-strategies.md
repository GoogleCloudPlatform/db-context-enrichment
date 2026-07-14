# Dataset Expansion Strategies
This document defines the expansion strategies used by the `dataset_expansion` phase in the context-engineering-dataset-generation skill. 

For every generated pair, use the Chain of Thought below regardless of strategy, then apply the **Operational Validation Gate** defined in `<skill_dir>/references/acceptance-criteria.md`.

## Chain of Thought (All Strategies)

For every candidate:
1. **Draft SQL (Schema-First):** Write syntactically correct, dialect-compliant SQL. Use only columns and tables confirmed in the schema. Ensure any `LIMIT` or window function includes a tie-breaking `ORDER BY`.
2. **Literal Translation:** Translate the SQL literally into English to surface all logical constraints.
3. **Humanize & Bridge:** Rewrite into natural business language. Never leak raw column names into the NLQ.
4. **Blind Test:** Looking only at the NLQ and business context — could another agent produce the exact SQL? If ambiguous, refine or discard.

---

#### Strategy 1: Paraphrasing

**Goal:** Reword the NLQ into a semantically equivalent question while keeping the SQL 100% unchanged.

**When to apply:** Any pair in the source dataset. Highly recommended for pairs with `complexity: low` or `complexity: medium` as they have simpler, more universally rephraseable NLQs.

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

**Anti-pattern:** Do not count changing `region = 'East'` to `region = 'West'` without also verifying the new value actually exists in the database and the query returns rows.
