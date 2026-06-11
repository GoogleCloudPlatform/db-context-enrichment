# Acceptance Criteria

## 1. Strict Schema Fidelity (Zero Hallucination)

* **Rule:** The SQL must exclusively use the tables, columns, data types, and relationships explicitly provided in the schema context.
* **Enforcement:** Do not invent missing columns, guess foreign key relationships, or assume standard system columns (e.g., `created_at`, `is_deleted`) exist unless documented.

## 2. Execution-Guided Validation

* **Rule:** The generated SQL must be syntactically flawless and capable of executing against the target dialect.
* **Enforcement:** Where possible, verify execution (e.g., via `<source>-execute-sql` MCP tool). Reject queries that result in syntax errors, data type mismatches, or logically impossible conditions that guarantee 0 rows (e.g., mutually exclusive `WHERE` filters).

## 3. The "Blind" Reversibility Test

* **Rule:** The natural language question (NLQ) and the provided business context must contain sufficient information to deterministically generate the exact SQL logic without looking at the answer.
* **Enforcement:** Evaluate the pair blindly. If another agent or human SME cannot deduce the necessary filters, groupings, or aggregations from the NLQ alone, the NLQ is too vague. Conversely, the NLQ must remain conversational—do not simply dictate the SQL structure in English (e.g., avoid "Select column A from table B where...").

## 4. Deterministic Output

* **Rule:** The SQL query must yield consistently reproducible results, independent of the database engine's default sorting behavior.
* **Enforcement:** Any query utilizing limits or window functions (e.g., "Top 10", "Most recent", `LIMIT`, `ROW_NUMBER()`) **must** include a robust `ORDER BY` clause. If sorting by a non-unique column (like `total_sales`), a unique tie-breaker (like `customer_id`) must be appended to the sort order.

## 5. Business Realism & Logical Coherence

* **Rule:** The NLQ must represent a plausible, real-world business question that a user would actually ask.
* **Enforcement:** Reject queries that perform mathematically invalid or meaningless operations (e.g., averaging phone numbers, summing categorical IDs, or joining unrelated tables just to increase complexity).

## 6. SQL Best Practices & Structure

* **Rule:** The SQL must follow modern, readable engineering standards.
* **Enforcement:**
* Use explicit `JOIN ... ON` syntax instead of implicit, comma-separated `FROM` clauses.
* Avoid accidental Cartesian products; all joins must have valid conditions.
* Apply descriptive aliases (`AS`) for tables and aggregated columns.
* Format queries with proper indentation and capitalized keywords for readability.