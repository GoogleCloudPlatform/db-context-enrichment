# Bigtable (GoogleSQL / BTQL) Template Generation Reference

This reference provides best practices, syntax specifications, and ideal output definitions for generating Templates in Bigtable (BTQL / GoogleSQL).

## Concepts

Templates map full natural language questions to full, executable SQL queries. In Cloud Bigtable (BTQL), templates teach the system overarching operational logic for querying wide-column data stored in a single table, navigating column families, decoding byte-encoded cell values, and filtering on row keys.

## BTQL Data Model for Templates

Bigtable represents data in a sorted wide-column model exposed through BTQL as a single relational table per query:

1. **Single Table in `FROM`**: Queries must always target exactly one table in the `FROM` clause. Multi-table joins are not supported.
2. **Backtick Identifier Quoting**: Table names, column families, and aliases should be enclosed in backticks (e.g., `` `hotels` ``, `` `hotel-bookings` ``) to prevent conflicts with reserved keywords or special characters like hyphens.
3. **Row Key Access (`_key`)**: The primary row key is accessible via the special `_key` column (type `BYTES`), which can be filtered using exact match (`_key = 'hotel#001'`), inequality (`_key >= 'hotel#100'`), or prefix matching (`_key LIKE 'hotel#%'`).
4. **Column Family Map Subscript**: Qualifiers within a column family are accessed using map subscript bracket notation `cf['qualifier']` (or `cf[b'qualifier']`), e.g., `info['city']` or `rating['score']`. If a qualifier does not exist for a given row, the expression evaluates cleanly to `NULL`.
5. **Explicit Type Decoders**: Raw cell values are stored as `BYTES`. Queries must use explicit converter and cast functions to decode bytes into typed scalar values:
   - **Strings**: `CAST(cf['qualifier'] AS STRING)` or `SAFE_CAST(cf['qualifier'] AS STRING)`
   - **64-bit Integers**: `TO_INT64(cf['qualifier'])` or `SAFE.TO_INT64(cf['qualifier'])`
   - **32-bit Integers**: `TO_INT32(cf['qualifier'])`
   - **64-bit Floats (Double)**: `TO_FLOAT64(cf['qualifier'])` or `SAFE.TO_FLOAT64(cf['qualifier'])`
   - **32-bit Floats**: `TO_FLOAT32(cf['qualifier'])`

## Parameterization

Values in the SQL query and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Template JSON Schema

```json
{
  "templates": [
    {
      "nl_query": "string (example user question)",
      "sql": "string (concrete executable BTQL query)",
      "intent": "string (specific intent of the query)",
      "manifest": "string (generalized description with 'a given <type>')",
      "parameterized": {
        "parameterized_sql": "string (BTQL query with '?' placeholders)",
        "parameterized_intent": "string (intent with '?' placeholders)"
      }
    }
  ]
}
```

### Examples

#### Example 1: String Attribute Filter and Count

**Input**:
*   **Question**: "How many hotels are located in Seattle?"
*   **SQL**: ``SELECT count(*) FROM `hotels` WHERE CAST(address['city'] AS STRING) = 'Seattle'``
*   **Intent**: "count of hotels in Seattle"

**Generated Output**:
```json
{
  "nl_query": "How many hotels are located in Seattle?",
  "sql": "SELECT count(*) FROM `hotels` WHERE CAST(address['city'] AS STRING) = 'Seattle'",
  "intent": "count of hotels in Seattle",
  "manifest": "count of hotels in a given city",
  "parameterized": {
    "parameterized_sql": "SELECT count(*) FROM `hotels` WHERE CAST(address['city'] AS STRING) = ?",
    "parameterized_intent": "count of hotels in ?"
  }
}
```

#### Example 2: Numeric Range and Decoded Metrics

**Input**:
*   **Question**: "Find all hotels with a rating greater than or equal to 4.5"
*   **SQL**: ``SELECT CAST(_key AS STRING) AS hotel_id, CAST(info['name'] AS STRING) AS name, TO_FLOAT64(rating['score']) AS rating FROM `hotels` WHERE TO_FLOAT64(rating['score']) >= 4.5 ORDER BY rating DESC LIMIT 50``
*   **Intent**: "hotels with rating at least 4.5"

**Generated Output**:
```json
{
  "nl_query": "Find all hotels with a rating greater than or equal to 4.5",
  "sql": "SELECT CAST(_key AS STRING) AS hotel_id, CAST(info['name'] AS STRING) AS name, TO_FLOAT64(rating['score']) AS rating FROM `hotels` WHERE TO_FLOAT64(rating['score']) >= 4.5 ORDER BY rating DESC LIMIT 50",
  "intent": "hotels with rating at least 4.5",
  "manifest": "hotels with rating at least a given number",
  "parameterized": {
    "parameterized_sql": "SELECT CAST(_key AS STRING) AS hotel_id, CAST(info['name'] AS STRING) AS name, TO_FLOAT64(rating['score']) AS rating FROM `hotels` WHERE TO_FLOAT64(rating['score']) >= ? ORDER BY rating DESC LIMIT 50",
    "parameterized_intent": "hotels with rating at least ?"
  }
}
```

#### Example 3: Grouping and Aggregation

**Input**:
*   **Question**: "What is the average room price for hotels in London?"
*   **SQL**: ``SELECT CAST(address['city'] AS STRING) AS city, AVG(TO_FLOAT64(pricing['room_rate'])) AS avg_price FROM `hotels` WHERE CAST(address['city'] AS STRING) = 'London' GROUP BY city``
*   **Intent**: "average room price in London"

**Generated Output**:
```json
{
  "nl_query": "What is the average room price for hotels in London?",
  "sql": "SELECT CAST(address['city'] AS STRING) AS city, AVG(TO_FLOAT64(pricing['room_rate'])) AS avg_price FROM `hotels` WHERE CAST(address['city'] AS STRING) = 'London' GROUP BY city",
  "intent": "average room price in London",
  "manifest": "average room price in a given city",
  "parameterized": {
    "parameterized_sql": "SELECT CAST(address['city'] AS STRING) AS city, AVG(TO_FLOAT64(pricing['room_rate'])) AS avg_price FROM `hotels` WHERE CAST(address['city'] AS STRING) = ? GROUP BY city",
    "parameterized_intent": "average room price in ?"
  }
}
```

## Unsupported BTQL Constructs for Templates

When authoring templates for Bigtable, do not use the following SQL constructs as they are unsupported by the BTQL query engine:

| Unsupported Construct | Description | BTQL Restriction & Alternative |
|-----------------------|-------------|--------------------------------|
| **`JOIN`** | `INNER JOIN`, `LEFT JOIN`, `FULL JOIN`, `CROSS JOIN` | Multi-table joins are disallowed. All queries must target a single table in `FROM`. |
| **`WITH` (CTEs)** | Common Table Expressions (`WITH cte AS (...)`) | CTEs are not supported. Write flat `SELECT ... FROM` statements. |
| **Subqueries** | Scalar subqueries, subqueries in `WHERE`/`SELECT`/`FROM` | Subqueries are not supported. All filtering must use direct column/map expressions. |
| **`OFFSET`** | Paging with `OFFSET` (e.g., `LIMIT 10 OFFSET 20`) | `OFFSET` is not supported. Use row key boundaries (`_key > 'last_seen_key'`) and `LIMIT n`. |
| **Direct Map Ordering** | `ORDER BY cf` (where `cf` is a MAP column) | Ordering directly on a map column is disallowed. Order by decoded scalar fields (e.g. `ORDER BY TO_INT64(cf['col'])`) or `_key`. |
| **Spanner Search Functions** | `SEARCH_NGRAMS()`, `SCORE_NGRAMS()`, `TOKENLIST` | Spanner search index functions are invalid in Bigtable. Use exact string equality or prefix filtering. |

## Best Practices

*   **Single Table Targeting**: Ensure every query specifies exactly one table in the `FROM` clause.
*   **Backtick Quoting**: Always wrap table names in backticks (e.g., `` `hotels` ``).
*   **Explicit Decoding**: Always apply explicit decoders (`CAST(... AS STRING)`, `TO_INT64(...)`, `TO_FLOAT64(...)`) when referencing qualifiers from column family maps.
*   **Row Key Optimization**: Utilize `_key` equality or prefix matching (`_key LIKE 'prefix%'`) where possible for optimal Bigtable scan performance.
*   **Parameterization**: Parameterize all literal filter values using `?` in `parameterized_sql` and `parameterized_intent` following the shared guidelines.
*   **Accurate Intents**: The intent must clearly describe what the query does and match the natural language question.
