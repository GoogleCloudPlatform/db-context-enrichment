# Spanner PostgreSQL Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in Cloud Spanner PostgreSQL.

## Concepts

Templates map full natural language questions to full SQL queries. They are used to teach the system overarching operational logic.

## Parameterization

Values in the SQL query and the intent must be replaced with positional parameters like `$1`, `$2`, etc., according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Question**: "How many accounts are in London?"
*   **SQL**: `SELECT count(*) FROM "account" WHERE "city" = 'London'`
*   **Intent**: "How many accounts are in London?"

**Generated Output** (Conceptual):
```json
{
  "nl_query": "How many accounts are in London?",
  "sql": "SELECT count(*) FROM \"account\" WHERE \"city\" = 'London'",
  "intent": "How many accounts are in London?",
  "manifest": "How many accounts are in a given city?",
  "parameterized": {
    "parameterized_sql": "SELECT count(*) FROM \"account\" WHERE \"city\" = $1",
    "parameterized_intent": "How many accounts are in $1?"
  }
}
```

## Best Practices

*   Provide complete, executable SQL queries.
*   Ensure the SQL follows Cloud Spanner PostgreSQL syntax:
    *   **Identifier Quoting**: Use standard ANSI double quotes (`"table"`, `"column"`). **Never use backticks** (`` `table` ``), which are invalid in PostgreSQL and Spanner PostgreSQL.
    *   **Positional Parameters**: Always use `$1`, `$2`, `$3` for parameterization (do not use `?`).
    *   **Functions**: Use PostgreSQL standard functions: `COALESCE()` (instead of `IFNULL`), `TO_CHAR()` / `DATE_TRUNC()` (instead of `FORMAT_DATE`), and `||` for string concatenation. For UUIDs in Cloud Spanner PostgreSQL, use `spanner.generate_uuid()` or `gen_random_uuid()`.
    *   **Types**: Cloud Spanner PostgreSQL data types (`bool`, `bigint`, `int8`, `float4`, `float8`, `date`, `timestamptz`, `interval`, `varchar`, `text`, `jsonb`, `numeric`, `bytea`, `uuid`). Only 1-dimensional arrays of these supported types.
*   The intent should accurately describe what the query does.
