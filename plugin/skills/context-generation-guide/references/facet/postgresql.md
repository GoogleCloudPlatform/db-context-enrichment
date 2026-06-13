# PostgreSQL Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in PostgreSQL.

## Concepts

Facets are reusable, modular SQL fragments (like a `WHERE` clause or specialized join). They are dynamically injected filters linked to specific vocabulary or terminology.

## Fully-Qualified Column References

Every column reference in a facet's SQL snippet **must** be qualified with its table name as `table.column` (e.g., `products.rating`). Facets are injected into larger queries that may join multiple tables, so unqualified columns risk ambiguity errors or silently binding to the wrong column. Never use table aliases — the surrounding query controls aliasing.

## Parameterization

Values in the SQL snippet and the intent must be replaced with positional parameters like `$1`, `$2`, etc., according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

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
    "parameterized_sql_snippet": "products.rating > $1",
    "parameterized_intent": "highly rated products (above $1)"
  }
}
```

## Best Practices

*   Provide clear and reusable SQL snippets.
*   **Always qualify columns as `table.column`** in both the literal and parameterized SQL snippets. Never use bare column names or table aliases.
*   Ensure the SQL snippet follows PostgreSQL syntax.
*   The intent should clearly describe the condition or filter.
