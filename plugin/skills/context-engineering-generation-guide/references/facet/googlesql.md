# Spanner (GoogleSQL) Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in Spanner (GoogleSQL).

## Concepts

Facets are reusable, modular SQL fragments (like a `WHERE` clause or specialized join). They are dynamically injected filters linked to specific vocabulary or terminology.

## Fully-Qualified Column References

Every column reference in a facet's SQL snippet **must** be qualified with its table name as `table.column` (e.g., `products.rating`). Facets are injected into larger queries that may join multiple tables, so unqualified columns risk ambiguity errors or silently binding to the wrong column. Never use table aliases — the surrounding query controls aliasing.

## Parameterization

Values in the SQL snippet and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example 1: Relational Column Filter

**Input**:
*   **SQL Snippet**: `products.rating > 4.5`
*   **Intent**: "highly rated products (above 4.5)"

**Generated Output** (Conceptual):
```json
{
  "sql_snippet": "products.rating > 4.5",
  "intent": "highly rated products (above 4.5)",
  "manifest": "highly rated products (above a given number)",
  "parameterized": {
    "parameterized_sql_snippet": "products.rating > ?",
    "parameterized_intent": "highly rated products (above ?)"
  }
}
```

### Example 2: Spanner Graph Pattern & Traversal Facet

For Spanner Graph, facets can represent reusable graph MATCH patterns, edge filter criteria, or traversal filters.

**Input**:
*   **SQL Snippet**: `MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE emp.jobtitle_normalised = 'Software Engineer'`
*   **Intent**: "experts working as Software Engineer"

**Generated Output** (Conceptual):
```json
{
  "sql_snippet": "MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE emp.jobtitle_normalised = 'Software Engineer'",
  "intent": "experts working as Software Engineer",
  "manifest": "experts working as a given job title",
  "parameterized": {
    "parameterized_sql_snippet": "MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE emp.jobtitle_normalised = ?",
    "parameterized_intent": "experts working as ?"
  }
}
```

## Best Practices

*   Provide clear and reusable SQL or GQL pattern snippets.
*   **Always qualify relational columns as `table.column`** in relational SQL snippets.
*   For graph pattern facets, specify the relevant node/edge labels and property filters.
*   Ensure the SQL/GQL snippet follows Spanner (GoogleSQL) syntax.
*   The intent should clearly describe the condition or filter.
