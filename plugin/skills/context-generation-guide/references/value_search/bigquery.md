# BigQuery (GoogleSQL) Value Search Templates

This reference provides the SQL templates and examples for Value Search in BigQuery (GoogleSQL).

## Requirements

*   Every table reference **must** be fully qualified as `` `{project}`.`{dataset}`.`{table}` `` — BigQuery has no default dataset at query time.
*   **BigQuery bills by bytes scanned.** Value searches run at query time for every matching user question, so a good value search is one that runs efficiently in both latency and cost. Keep the scanned column set minimal and prefer small, low-cardinality tables (see the per-function performance recommendations below).

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings in BigQuery.
**Example**: Use for exact IDs or state codes.

**Template**:
```sql
SELECT CAST($value AS STRING) AS value, '{column}' AS `columns`,
'{concept_type}' AS concept_type, 0.0 AS distance,
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

### 3. SEMANTIC_SIMILARITY_MATCH

**Description**: Semantic similarity search using a BigQuery ML remote embedding model over Vertex AI (e.g., `text-embedding-005`).
**Prerequisites**: Requires a remote model created with `CREATE MODEL ... REMOTE WITH CONNECTION ... OPTIONS (ENDPOINT = 'text-embedding-005')` (referenced below as `{embedding_model}`) and a pre-computed `{column_embedding}` column of type `ARRAY<FLOAT64>` generated with the same model.
**Example**: Use when searching for concepts, descriptions, themes, or abstract text where the exact words might differ but the underlying meaning is similar.

**Performance Recommendations**:
*   **Pre-compute embeddings**: Do NOT call `ML.GENERATE_EMBEDDING` on `T.{column}` inline — that re-embeds every row on every query and is billed per row. Only the search value is embedded at query time.
*   **Create a vector index**: For large tables, create a vector index on `{column_embedding}` (`CREATE VECTOR INDEX ... OPTIONS (index_type = 'IVF', distance_type = 'COSINE')`) and switch to `VECTOR_SEARCH` to avoid a full scan.

**Template**:
```sql
WITH search_embedding AS (
  SELECT ml_generate_embedding_result AS val
  FROM ML.GENERATE_EMBEDDING(
    MODEL `{project}`.`{dataset}`.`{embedding_model}`,
    (SELECT CAST($value AS STRING) AS content),
    STRUCT(TRUE AS flatten_json_output)
  )
)
SELECT value, '{column}' AS `columns`, '{concept_type}' AS concept_type, distance,
JSON '{}' AS context
FROM (
  SELECT DISTINCT CAST(T.`{column}` AS STRING) AS value,
  ML.DISTANCE(T.`{column_embedding}`, search_embedding.val, 'COSINE') / 2.0 AS distance
  FROM `{project}`.`{dataset}`.`{table}` AS T, search_embedding
  WHERE T.`{column_embedding}` IS NOT NULL
)
```
