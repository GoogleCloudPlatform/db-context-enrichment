# BigQuery (GoogleSQL) Value Search Templates

This reference provides the SQL templates and examples for Value Search in BigQuery (GoogleSQL).

## Requirements

*   Every table reference **must** be fully qualified as `` `{project}`.`{dataset}`.`{table}` `` — BigQuery has no default dataset at query time.

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings in BigQuery.
**Example**: Use for exact IDs or state codes.

**Template**:
```sql
SELECT CAST($value AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type, 0 AS distance,
JSON '{}' AS context
FROM `{project}`.`{dataset}`.`{table}` AS T
WHERE CAST(T.`{column}` AS STRING) = CAST($value AS STRING)
```

### 2. EDIT_DISTANCE_MATCH

**Description**: String similarity using BigQuery's built-in `EDIT_DISTANCE` function (Levenshtein distance). No index prerequisites.
**Example**: Use for typos/misspellings (e.g., "Lndn" → "London").

**Template**:
```sql
SELECT CAST(T.`{column}` AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type,
EDIT_DISTANCE(LOWER(CAST(T.`{column}` AS STRING)), LOWER(CAST($value AS STRING))) AS distance,
JSON '{}' AS context
FROM `{project}`.`{dataset}`.`{table}` AS T
WHERE EDIT_DISTANCE(LOWER(CAST(T.`{column}` AS STRING)), LOWER(CAST($value AS STRING))) <= 3
```

**Performance Recommendations**:
*   Value-search scans are full-table scans in BigQuery. Prefer running them against low-cardinality dimension tables, or pre-materialize a `SELECT DISTINCT {column}` lookup table to bound bytes scanned.
