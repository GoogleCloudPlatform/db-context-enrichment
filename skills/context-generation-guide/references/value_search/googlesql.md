# Spanner (GoogleSQL) Value Search Templates

This reference provides the SQL templates and examples for Value Search in Spanner (GoogleSQL).

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

### 3. SEMANTIC_SIMILARITY_GEMINI

**Description**: Semantic search using Vector Search on string embeddings.
**Prerequisites**: Requires an embedding model (e.g., registered in Spanner) and an embedding column.
**Example**: Use for conceptual search or synonym matching in Spanner.

**Performance Recommendations**:
*   Create a Search Index with `distance_type => 'COSINE'` on the embedding column to accelerate vector search.

**Template**:
```sql
WITH value_embedding AS (
    SELECT embeddings.values 
    FROM ML.PREDICT(
        MODEL {EmbedModel}, 
        (SELECT @value AS content))
)
SELECT T.`{column}` AS value, 
       '{column}' AS `columns`, 
       '{concept_type}' AS concept_type,
       COSINE_DISTANCE(
         T.`{column_embedding}`, 
         value_embedding.values) AS distance, 
       JSON '{}' AS context, 
       T.PK AS primary_key 
FROM `{table}` AS T, value_embedding
WHERE T.`{column_embedding}` IS NOT NULL 
ORDER BY distance ASC LIMIT 10
```
