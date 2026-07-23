# BigQuery (GoogleSQL) Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in BigQuery (GoogleSQL).

## Concepts

Templates map full natural language questions to full SQL queries. They are used to teach the system overarching operational logic.

## Fully-Qualified Table References (CRITICAL)

Unlike Postgres or Spanner connections, a BigQuery connection is scoped to a
project only — there is **no default dataset at query time**. Every table
reference in the SQL **must** be fully qualified as
`` `<project>`.`<dataset>`.`<table>` `` (e.g.,
`` `my-project`.`sales_data`.`orders` ``). SQL that references a bare table
name (`FROM orders`) will fail with "Table not found" when executed.

Take the project and dataset IDs from the `kind: source` block in
`tools.yaml`. Apply this rule to the `sql` field AND the
`parameterized_sql` field — never parameterize the project, dataset, or
table identifiers themselves; only parameterize filter values.

## Parameterization

Values in the SQL query and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Question**: "How many accounts are in London?"
*   **SQL**: ``SELECT count(*) FROM `my-project`.`finance`.`account` WHERE city = 'London'``
*   **Intent**: "How many accounts are in London?"

**Generated Output** (Conceptual):
```json
{
  "nl_query": "How many accounts are in London?",
  "sql": "SELECT count(*) FROM `my-project`.`finance`.`account` WHERE city = 'London'",
  "intent": "How many accounts are in London?",
  "manifest": "How many accounts are in a given city?",
  "parameterized": {
    "parameterized_sql": "SELECT count(*) FROM `my-project`.`finance`.`account` WHERE city = ?",
    "parameterized_intent": "How many accounts are in ?"
  }
}
```

## Best Practices

*   Provide complete, executable SQL queries.
*   Ensure the SQL follows BigQuery (GoogleSQL) syntax.
*   **Always fully qualify every table as `` `project`.`dataset`.`table` ``** in both `sql` and `parameterized_sql`.
*   The intent should accurately describe what the query does.
