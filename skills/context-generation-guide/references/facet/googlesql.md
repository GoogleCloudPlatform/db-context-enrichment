# Spanner (GoogleSQL) Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in Spanner (GoogleSQL).

## Concepts

Facets are reusable, modular SQL fragments (like a `WHERE` clause or specialized join). They are dynamically injected filters linked to specific vocabulary or terminology.

## Parameterization

Values in the SQL snippet and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **SQL Snippet**: `rating > 4.5`
*   **Intent**: "highly rated products (above 4.5)"

**Generated Output** (Conceptual):
```json
{
  "sql_snippet": "rating > 4.5",
  "intent": "highly rated products (above 4.5)",
  "manifest": "highly rated products (above a given number)",
  "parameterized": {
    "parameterized_sql_snippet": "rating > ?",
    "parameterized_intent": "highly rated products (above ?)"
  }
}
```

## Best Practices

*   Provide clear and reusable SQL snippets.
*   Ensure the SQL snippet follows Spanner (GoogleSQL) syntax.
*   The intent should clearly describe the condition or filter.
