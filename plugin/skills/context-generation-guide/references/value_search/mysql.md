# MySQL Value Search Templates

This reference provides the SQL templates and examples for Value Search in MySQL.

## Requirements

*   **Minimum MySQL version**: `8`.

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings in MySQL.
**Example**: Use for exact matching in MySQL.

**Note**: Deduping (`GROUP BY`) happens in a subquery on non-`JSON` columns; the `JSON_OBJECT() AS context` literal is projected in the outer query. MySQL does not allow `JSON` columns in `DISTINCT`/`GROUP BY`, and under `ONLY_FULL_GROUP_BY` a non-grouped `JSON` column can't be selected alongside a `GROUP BY`.

**Template**:
```sql
SELECT value, `columns`, concept_type, distance, JSON_OBJECT() AS context
FROM (
  SELECT $value AS value, '{column}' AS `columns`,
  '{concept_type}' AS concept_type, 0 AS distance
  FROM `{table}` AS T WHERE T.`{column}` = $value
  GROUP BY value, `columns`, concept_type, distance
) AS T
```

### 2. TRIGRAM_STRING_MATCH

**Description**: Trigram fuzzy match in MySQL using FULLTEXT index with score normalization.
**Prerequisites**: Requires a `FULLTEXT` index on the column, ideally with an `ngram` parser for better trigram support.
**Example**: Use for fuzzy matching in MySQL (requires `FULLTEXT` index).

**Performance Recommendations**:
*   Use a `FULLTEXT` index with the `ngram` parser for trigram-like behavior:
    ```sql
    ALTER TABLE `{table}` ADD FULLTEXT INDEX ft_ngram_idx (`{column}`) WITH PARSER ngram;
    ```

**Template**:
```sql
SELECT value, `columns`, concept_type, distance, JSON_OBJECT() AS context
FROM (
  WITH TrigramMetrics AS (
    SELECT T.`{column}` AS original_value,
    MATCH(T.`{column}`) AGAINST($value IN NATURAL LANGUAGE MODE) AS raw_score
    FROM `{table}` AS T
    WHERE MATCH(T.`{column}`) AGAINST($value IN NATURAL LANGUAGE MODE) > 0
    ORDER BY raw_score DESC LIMIT 10
  ),
  NormalizationParams AS (
    SELECT MAX(raw_score) AS max_score
    FROM TrigramMetrics
  )
  SELECT original_value AS value, '{column}' AS `columns`,
  '{concept_type}' AS concept_type,
  (CASE WHEN n.max_score > 0 THEN (1 - (m.raw_score / n.max_score)) ELSE 0 END) AS distance
  FROM TrigramMetrics m, NormalizationParams n
) AS wrapped_query
GROUP BY value, `columns`, concept_type, distance
```

### 3. SEMANTIC_SIMILARITY_MATCH

**Description**: Semantic match in MySQL using Vertex AI embedding.
**Prerequisites**: Requires `mysql.ml_embedding` support and a `column_embedding` column.
**Example**: Use for semantic matching (requires `mysql.ml_embedding`).

**Performance Recommendations**:
*   **Pre-compute embeddings**: MySQL cannot call Gemini models inline efficiently for large datasets. Pre-compute embeddings and store them in a column (e.g., `{column_embedding}`).
*   **Use a VECTOR index**: Use a `VECTOR` index (available in HeatWave or specialized builds) to accelerate distance calculations.

**Template**:
```sql
SELECT value, `columns`, concept_type, distance, JSON_OBJECT() AS context
FROM (
  WITH search_embedding AS (
    SELECT mysql.ml_embedding('text-embedding-005', $value) AS val
  )
  SELECT T.`{column}` AS value, '{column}' AS `columns`,
  '{concept_type}' AS concept_type,
  COSINE_DISTANCE(T.`{column_embedding}`, search_embedding.val) AS distance
  FROM `{table}` AS T, search_embedding
  WHERE T.`{column_embedding}` IS NOT NULL
) AS wrapped_query
GROUP BY value, `columns`, concept_type, distance
```
