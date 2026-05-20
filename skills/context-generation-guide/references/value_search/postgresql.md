# PostgreSQL Value Search Templates

This reference provides the SQL templates and examples for Value Search in PostgreSQL.

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for strings (Standard SQL).
**Example**: Use when finding a specific state code (e.g., 'CA'), order ID, or exact product name where precise spelling is required.

**Template**:
```sql
SELECT $value as value, '{table}.{column}' as columns, '{concept_type}' as concept_type, 0 as distance, '' as context FROM "{table}" T WHERE T."{column}" = $value
```

### 2. TRIGRAM_STRING_MATCH

**Description**: Fuzzy text match using trigram similarity.
**Prerequisites**: Requires `pg_trgm` extension.
**Example**: Use when searching for names, addresses, or plain text where users might have typos, misspellings, or partial matches.

**Performance Recommendations**:
*   Use a GiST index on the search column to accelerate trigram distance calculations:
    ```sql
    CREATE INDEX idx_trgm_gist ON "{table}" USING gist ("{column}" gist_trgm_ops);
    ```
*   The template uses the `%` operator in the `WHERE` clause to discard bad matches early and utilize the index.

**Template**:
```sql
WITH TrigramMetrics AS (
    SELECT T."{column}" AS original_value,
    (T."{column}" <-> $value::text) AS normalized_dist
    FROM "{table}" T
    WHERE T."{column}" % $value::text
)
SELECT original_value AS value, '{table}.{column}' AS columns,
'{concept_type}' AS concept_type, normalized_dist AS distance,
''::text AS context FROM TrigramMetrics
```

### 3. SEMANTIC_SIMILARITY_MATCH

**Description**: Semantic similarity search using Gemini text embeddings.
**Prerequisites**: Requires `vector` and `google_ml_integration` extensions.
**Example**: Use when searching for concepts, descriptions, themes, or abstract text where the exact words might differ but the underlying meaning is similar.

**Performance Recommendations**:
*   **Pre-compute embeddings**: If the column has a corresponding embedding column, replace the inline `google_ml.embedding` call for `T."{column}"` with the name of the embedding column.
*   **Create a Vector Index**: Create an index (e.g., HNSW or IVFFlat) on the embedding column to speed up the `<=>` (cosine distance) operations.

**Template**:
```sql
WITH SemanticMetrics AS (
    SELECT T."{column}" AS original_value, (
        (google_ml.embedding('gemini-embedding-001', $value)::vector <=>
         google_ml.embedding('gemini-embedding-001', T."{column}")::vector) / 2.0
    ) AS normalized_dist
    FROM "{table}" T
    WHERE T."{column}" IS NOT NULL
)
SELECT original_value AS value, '{table}.{column}' AS columns,
'{concept_type}' AS concept_type, normalized_dist AS distance,
''::text AS context FROM SemanticMetrics
```
