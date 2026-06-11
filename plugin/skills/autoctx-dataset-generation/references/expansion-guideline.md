# NL-to-SQL Dataset Expansion Guidelines

When expanding an existing dataset, your goal is to introduce meaningful variance that tests the robustness of an NL2SQL engine. Do not simply duplicate pairs with minor variable changes (e.g., changing "2023" to "2024"). Instead, apply the following multidimensional expansion strategies.

## 1. Constraint Layering (Increasing Complexity)
Take a base query and add intersecting business logic, filtering, or grouping requirements to increase the SQL complexity (e.g., forcing new `JOIN`s, `GROUP BY`s, or `HAVING` clauses).
*   **Base:** "Show me total sales." -> `SELECT SUM(amount) FROM sales;`
*   **Layer 1 (Filter):** "Show me total sales for enterprise customers." -> Requires `JOIN` to customers table.
*   **Layer 2 (Grouping + Condition):** "Show me total sales by region, but only for regions with more than 5 enterprise customers." -> Requires `GROUP BY` and `HAVING`.
*   **Layer 3 (Temporal):** "...comparing this quarter to last quarter." -> Requires Window Functions or Self-Joins.

## 2. Lexical & Conversational Variance (Increasing NLQ Difficulty)
Keep the underlying SQL logic exactly the same, but drastically alter how the human asks the question to test semantic mapping.
*   **Synonyms & Slang:** Replace exact schema column names with business jargon. ("revenue" instead of `total_amount`, "churned" instead of `is_active = false`).
*   **Implicit Intent:** Remove explicit instructions. (Explicit: "List users ordered by signup date descending." -> Implicit: "Who are our newest users?")
*   **Conversational Shorthand:** Use fragmented or conversational phrasing ("Any accounts without a billing zip?", "Who's our top rep this month?").

## 3. Pattern Transposition (Cross-Schema Shifting)
Identify a complex SQL pattern used in one domain and apply it to a completely different set of tables in the schema. 
*   **Pattern:** The "Anti-Join" (Entities lacking a related record).
*   **Source Entity:** "Show me customers who haven't placed an order." 
*   **Shifted Entity:** "Show me support agents who haven't closed a ticket this week."

## 4. Edge Case & Robustness Testing
Generate pairs that test how the model handles tricky database states and edge-case business logic.
*   **Handling NULLs/Empties:** "Show me users who never set a profile picture." (`WHERE avatar_url IS NULL`).
*   **Soft Deletes:** Ensure the user's intent requires filtering out soft-deleted records (e.g., `is_deleted = false` or `status != 'archived'`).
*   **Ambiguous Timeframes:** "Recent," "last month," "YTD." (Map these to explicit, mathematically sound SQL date functions based on the current system date).

## Expansion Guardrails (Anti-Patterns to Avoid)
1.  **Lazy Parameter Swapping:** Do NOT count changing `region = 'East'` to `region = 'West'` as a new pair. It must test a different structural or linguistic vector.
2.  **Over-complication:** Do not build "Frankenstein" queries with 8+ joins unless explicitly asked to generate a "Hard/Complex" pair.
3.  **Schema Drift:** All expanded pairs must strictly adhere to the provided schema. Do not invent tables to satisfy an expansion idea.