# Generation Plan Composition Requirements

A generation plan (whether newly drafted or modified) must explicitly define the following parameters:

1. **Structural Architecture:** Expected usage of CTEs vs. subqueries, window functions, and explicit vs. implicit JOINs.
2. **Business Rules & Filtering:** Standardized WHERE/HAVING clauses (e.g., handling soft deletes, specific date bounding).
3. **NLQ-to-SQL Semantic Mapping:** Exact SQL operations required for ambiguous business terms (e.g., "recent", "top").
4. **Schema Coverage:** Target distribution metrics across the most critical tables.
5. **Complexity Distribution:** Percentage targets for simple, medium, and complex pairs based on user goals and context.
6. **Diversity Principles:** The intended mix of question types (e.g., aggregation, joins, nested queries) and business topics.
7. **Source Attribution:** Clear guidelines for how to tag pairs based on their origin (e.g., "query_log_seed", "schema_analysis", "business_doc_extraction").
