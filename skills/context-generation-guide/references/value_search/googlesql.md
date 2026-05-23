# Spanner (GoogleSQL) Value Search Templates

This reference provides the SQL templates and examples for Value Search in Spanner (GoogleSQL).

## Requirements

*   **`SEMANTIC_SIMILARITY_MATCH` is NOT supported** on Spanner. Only `EXACT_MATCH_STRINGS` and `TRIGRAM_STRING_MATCH` are available — do not author value searches that rely on semantic embeddings here.

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings in Spanner.
**Example**: Use for exact IDs or state codes in Spanner.

**Template**:
```sql
SELECT CAST($value AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type, 0 AS distance,
JSON '{}' AS context
FROM `{table}` AS T
WHERE CAST(T.`{column}` AS STRING) = CAST($value AS STRING)
```

### 2. TRIGRAM_STRING_MATCH

**Description**: String similarity using Spanner Search Indexes.
**Prerequisites**: Requires Spanner Search Indexes and a `column_tokens` column configured with `SEARCH_NGRAMS`.
**Example**: Use for typos/misspellings in Spanner using `SEARCH_NGRAMS`.

**Performance Recommendations**:
*   Use a Search Index on a `TOKENLIST` column (e.g., `{column_tokens}`) to accelerate search.

**Template**:
```sql
SELECT CAST(T.`{column}` AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type,
1 - SCORE_NGRAMS(T.`{column_tokens}`, CAST($value AS STRING)) AS distance,
JSON '{}' AS context
FROM `{table}` AS T
WHERE SEARCH_NGRAMS(T.`{column_tokens}`, CAST($value AS STRING))
```
