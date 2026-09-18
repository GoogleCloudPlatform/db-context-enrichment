# Bigtable (BTQL) Value Search Templates

This reference provides the SQL templates and examples for Value Search in Cloud Bigtable (BTQL).

## Requirements & Dialect Constraints

*   **`SEMANTIC_SIMILARITY_MATCH` is NOT supported** on Cloud Bigtable. Bigtable (BTQL) does not provide in-database vector embeddings or vector distance operators. Do not author value searches that rely on semantic embeddings.
*   **`TRIGRAM_STRING_MATCH` (and `SEARCH_NGRAMS`) is NOT supported** on Cloud Bigtable. Bigtable (BTQL) does not support full-text search indexes, trigram tokenizers, or fuzzy string operators. Do not author fuzzy or trigram value searches for Bigtable.
*   **Only `EXACT_MATCH_STRINGS` is supported** for Bigtable.
*   **Context column**: Uses `'' AS context` (empty string) because BTQL does not have a native JSON literal type or JSON constructor.
*   **Single-Table Scans**: All queries scan a single table or Logical View aliased as `T`.

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings in Bigtable (BTQL).  
**Example**: Use for exact matching in Bigtable (usually on Logical Views or string columns, e.g., finding a specific city, state code, hotel ID, or category name).

**Template**:
```sql
SELECT CAST(T.`{column}` AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type, 0 AS distance,
'' AS context
FROM `{table}` AS T
WHERE CAST(T.`{column}` AS STRING) = CAST($value AS STRING)
```

**Template Placeholders**:
*   `{table}`: The Bigtable table or Logical View name (enclosed in backticks).
*   `{column}`: The target column name (enclosed in backticks).
*   `{concept_type}`: The name of the conceptual entity (e.g., `'City'`, `'HotelID'`).
*   `$value`: The search value parameter passed dynamically at execution time.

## Example Generated Output (Conceptual)

```json
{
  "value_searches": [
    {
      "concept_type": "City",
      "query": "SELECT CAST(T.`city` AS STRING) AS value, 'city' AS `columns`, 'City' AS concept_type, 0 AS distance, '' AS context FROM `hotels` AS T WHERE CAST(T.`city` AS STRING) = CAST($value AS STRING)",
      "description": "Exact match for hotel city in hotels table"
    }
  ]
}
```

## Best Practices

*   **Use on Logical Views**: Prefer applying value searches against Bigtable Logical Views where column types and schemas are explicitly defined.
*   **Always Backtick Identifiers**: Wrap table names and column names in backticks (`` `...` ``) to avoid collisions with BTQL reserved keywords.
*   **Case Sensitivity**: BTQL `=` comparisons are case-sensitive. Ensure that search values match the expected database casing.
*   **Zero Distance**: Exact matches always set `0 AS distance`.
