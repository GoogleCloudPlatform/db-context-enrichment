# Bigtable (BTQL) Facet Generation Reference

This reference provides best practices, syntax specifications, and ideal output definitions for generating Facets in Bigtable (BTQL / GoogleSQL).

## Concepts

Facets are reusable, modular SQL fragments (typically boolean expressions evaluated in a `WHERE` or `HAVING` clause). They represent dynamically injected filters linked to specific domain terminology or natural language concepts.

In Cloud Bigtable (BTQL), facets filter rows from a single wide-column table or logical view. Because Bigtable stores cell data as raw bytes and organizes columns into column families, facet expressions must explicitly address column family maps, decode byte values into scalar types, and fully qualify all references.

## Fully-Qualified References & Identifier Quoting

Every column and map qualifier reference in a facet's SQL snippet **must** be fully qualified with its table name. Never use table aliases (e.g., `T.`, `h.`) — the surrounding query or generator controls aliasing when composing full queries.

### 1. Standard Bigtable Tables (Column Family Maps)
Column qualifiers belong to column families and are accessed using map subscript bracket notation:
- **Syntax**: `table.cf['qualifier']` (or `table.cf[b'qualifier']`)
- **Examples**:
  - `hotels.info['city']`
  - `hotels.rating['score']`
  - `` `hotel-bookings`.reservation['status'] ``

### 2. Row Key Access (`_key`)
The primary row key column is named `_key` (type `BYTES`):
- **Syntax**: `table._key`
- **Examples**:
  - `CAST(hotels._key AS STRING) LIKE 'hotel#100%'`
  - `hotels._key >= b'hotel#00100'`

### 3. Logical Views (Relational Columns)
When querying Bigtable Logical Views, columns are projected as standard relational identifiers:
- **Syntax**: `table.column`
- **Examples**:
  - `hotel_view.city`
  - `` `hotel-summary-view`.star_rating ``

### 4. Backtick Quoting
Table names or identifiers containing hyphens (`-`), numbers, keywords, or special characters must be enclosed in backticks (e.g., `` `hotel-reviews`.metrics['score'] ``). Qualifiers inside bracket subscripts are single-quoted string or byte literals (e.g., `cf['check-in-date']`).

## Type Decoding & Byte Conversions

Bigtable stores cell payloads as `BYTES`. When writing facet filter predicates against strings, integers, floats, or booleans, you must use explicit BTQL conversion and cast functions:

| Target Type | Conversion Function | Example Facet Predicate |
|-------------|---------------------|-------------------------|
| **String** | `CAST(table.cf['col'] AS STRING)` | `CAST(hotels.info['city'] AS STRING) = 'London'` |
| **Safe String** | `SAFE_CAST(table.cf['col'] AS STRING)` | `SAFE_CAST(hotels.info['city'] AS STRING) LIKE 'San%'` |
| **64-bit Integer** | `TO_INT64(table.cf['col'])` | `TO_INT64(hotels.details['capacity']) >= 4` |
| **32-bit Integer** | `TO_INT32(table.cf['col'])` | `TO_INT32(hotels.details['floor']) = 2` |
| **64-bit Float** | `TO_FLOAT64(table.cf['col'])` | `TO_FLOAT64(hotels.rating['score']) >= 4.5` |
| **32-bit Float** | `TO_FLOAT32(table.cf['col'])` | `TO_FLOAT32(hotels.pricing['tax_rate']) < 0.1` |
| **Raw Bytes** | Binary literal `b'...'` | `hotels.status['state'] = b'CONFIRMED'` |

### Map Functions in Facets
BTQL provides built-in map functions for inspecting column family structure directly in facet filters:
- **Key Existence**: `map_contains_key(hotels.amenities, 'swimming_pool')`
- **Empty Family Check**: `map_empty(hotels.discounts)`
- **Non-Empty Check**: `NOT map_empty(hotels.amenities)`

## Parameterization

Values in the SQL snippet and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Facet JSON Schema

```json
{
  "facets": [
    {
      "sql_snippet": "string (concrete SQL boolean predicate with fully-qualified columns and explicit decoders)",
      "intent": "string (specific intent of the facet filter)",
      "manifest": "string (generalized description replacing values with 'a given <type>')",
      "parameterized": {
        "parameterized_sql_snippet": "string (SQL snippet with '?' placeholders)",
        "parameterized_intent": "string (intent with '?' placeholders)"
      }
    }
  ]
}
```

## Examples

### Example 1: String Qualifier Equality Filter

**Input**:
*   **SQL Snippet**: `CAST(hotels.info['city'] AS STRING) = 'London'`
*   **Intent**: "hotels located in 'London'"

**Generated Output**:
```json
{
  "sql_snippet": "CAST(hotels.info['city'] AS STRING) = 'London'",
  "intent": "hotels located in 'London'",
  "manifest": "hotels located in a given city",
  "parameterized": {
    "parameterized_sql_snippet": "CAST(hotels.info['city'] AS STRING) = ?",
    "parameterized_intent": "hotels located in ?"
  }
}
```

### Example 2: Floating-Point Metric Filter with Decoder

**Input**:
*   **SQL Snippet**: `TO_FLOAT64(hotels.rating['score']) >= 4.5`
*   **Intent**: "hotels with rating at least 4.5"

**Generated Output**:
```json
{
  "sql_snippet": "TO_FLOAT64(hotels.rating['score']) >= 4.5",
  "intent": "hotels with rating at least 4.5",
  "manifest": "hotels with rating at least a given number",
  "parameterized": {
    "parameterized_sql_snippet": "TO_FLOAT64(hotels.rating['score']) >= ?",
    "parameterized_intent": "hotels with rating at least ?"
  }
}
```

### Example 3: Integer Capacity / Count Filter

**Input**:
*   **SQL Snippet**: `TO_INT64(hotels.room['capacity']) >= 4`
*   **Intent**: "rooms accommodating at least 4 guests"

**Generated Output**:
```json
{
  "sql_snippet": "TO_INT64(hotels.room['capacity']) >= 4",
  "intent": "rooms accommodating at least 4 guests",
  "manifest": "rooms accommodating at least a given number guests",
  "parameterized": {
    "parameterized_sql_snippet": "TO_INT64(hotels.room['capacity']) >= ?",
    "parameterized_intent": "rooms accommodating at least ? guests"
  }
}
```

### Example 4: Row Key Prefix Filter

**Input**:
*   **SQL Snippet**: `CAST(hotels._key AS STRING) LIKE 'hotel#100%'`
*   **Intent**: "hotels with ID prefix 'hotel#100'"

**Generated Output**:
```json
{
  "sql_snippet": "CAST(hotels._key AS STRING) LIKE 'hotel#100%'",
  "intent": "hotels with ID prefix 'hotel#100'",
  "manifest": "hotels with ID prefix a given product",
  "parameterized": {
    "parameterized_sql_snippet": "CAST(hotels._key AS STRING) LIKE ?",
    "parameterized_intent": "hotels with ID prefix ?"
  }
}
```

### Example 5: Map Key Existence Filter

**Input**:
*   **SQL Snippet**: `map_contains_key(hotels.amenities, 'swimming_pool')`
*   **Intent**: "hotels that have 'swimming_pool' amenity"

**Generated Output**:
```json
{
  "sql_snippet": "map_contains_key(hotels.amenities, 'swimming_pool')",
  "intent": "hotels that have 'swimming_pool' amenity",
  "manifest": "hotels that have a given product amenity",
  "parameterized": {
    "parameterized_sql_snippet": "map_contains_key(hotels.amenities, ?)",
    "parameterized_intent": "hotels that have ? amenity"
  }
}
```

### Example 6: Logical View Relational Column Filter

**Input**:
*   **SQL Snippet**: `` `hotel-summary-view`.city = 'Seattle' ``
*   **Intent**: "hotels in 'Seattle' from view"

**Generated Output**:
```json
{
  "sql_snippet": "`hotel-summary-view`.city = 'Seattle'",
  "intent": "hotels in 'Seattle' from view",
  "manifest": "hotels in a given city from view",
  "parameterized": {
    "parameterized_sql_snippet": "`hotel-summary-view`.city = ?",
    "parameterized_intent": "hotels in ? from view"
  }
}
```

## Unsupported BTQL Constructs in Facets

When authoring facets for Bigtable, the following constructs must never be used:

| Unsupported Construct | Description | BTQL Restriction & Rationale |
|-----------------------|-------------|------------------------------|
| **Multi-Table Joins** | `JOIN`, `INNER JOIN`, `LEFT JOIN` | Bigtable queries operate on a single table; multi-table joins are not supported. |
| **Subqueries** | `WHERE col IN (SELECT ...)` | BTQL does not support scalar or nested subqueries. |
| **Common Table Expressions (`WITH`)** | `WITH cte AS (...)` | CTEs are unsupported in BTQL. |
| **Spanner Search Functions** | `SEARCH_NGRAMS()`, `SCORE_NGRAMS()`, `TOKENLIST` | Search indexes are exclusive to Spanner; use `LIKE`, `STARTS_WITH`, or exact match in BTQL. |
| **Non-Standard String Operators** | `ILIKE`, `SIMILAR TO`, `~` | Not supported in GoogleSQL/BTQL; use `REGEXP_CONTAINS()` or standard `LIKE`. |
| **Unqualified Columns** | `info['city']`, `city` | All columns must be qualified with the table name (`table.cf['qualifier']` or `table.column`). |
| **Table Aliases** | `T.info['city']`, `h.city` | Never use table aliases in facets; the enclosing query manages aliasing. |

## Best Practices

*   **Always Fully Qualify References**: Use `table.cf['qualifier']` for base tables, `table._key` for row keys, and `table.column` for logical views in both literal and parameterized SQL snippets.
*   **Never Use Table Aliases**: Do not prefix columns with aliases like `T.` or `h.`.
*   **Explicit Type Decoding**: Apply explicit byte decoders (`CAST(... AS STRING)`, `TO_INT64(...)`, `TO_FLOAT64(...)`) to column family qualifiers because raw cell values are stored as `BYTES`.
*   **Backtick Quoting**: Always wrap table names and identifiers with hyphens or keywords in backticks (e.g. `` `hotel-reviews` ``).
*   **Parameterization with `?`**: Replace literal values in `parameterized_sql_snippet` and `parameterized_intent` using `?` according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).
*   **Clear and Descriptive Intents**: The intent must clearly describe the semantic filter condition represented by the facet.
