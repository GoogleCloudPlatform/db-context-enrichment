# PostgreSQL Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in PostgreSQL.

## Concepts

Templates map full natural language questions to full SQL queries. They are used to teach the system overarching operational logic.

## Parameterization

Values in the SQL query and the intent must be replaced with positional parameters like `$1`, `$2`, etc., according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Question**: "How many accounts are in London?"
*   **SQL**: `SELECT count(*) FROM account WHERE city = 'London'`
*   **Intent**: "How many accounts are in London?"

**Generated Output** (Conceptual):
```json
{
  "nl_query": "How many accounts are in London?",
  "sql": "SELECT count(*) FROM account WHERE city = 'London'",
  "intent": "How many accounts are in London?",
  "manifest": "How many accounts are in a given city?",
  "parameterized": {
    "parameterized_sql": "SELECT count(*) FROM account WHERE city = $1",
    "parameterized_intent": "How many accounts are in $1?"
  }
}
```

## Best Practices

*   Provide complete, executable SQL queries.
*   Ensure the SQL follows PostgreSQL syntax.
*   The intent should accurately describe what the query does.
