# Firestore (NoSQL MQL) Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in Firestore Native Mode and MongoDB MQL (`firestore_mql`).

## Concepts

Facets are modular, reusable NoSQL filter fragments or field-value predicates (such as `$match` stages or nested document predicates). They link natural language terminology to specific NoSQL query conditions.

## Parameterization

Values in the NoSQL snippet and intent are parameterized using positional placeholders (e.g. `$1`), according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Term / Concept**: "In store purchase method"
*   **NoSQL Snippet**: `sales.purchaseMethod = 'In store'`
*   **Intent**: "In store purchase method string format without hyphen"

**Generated Output**:
```json
{
  "sql_snippet": "sales.purchaseMethod = 'In store'",
  "intent": "in-store purchase method is literal string 'In store' (with space, no hyphen)",
  "manifest": "In store purchase method string format without hyphen",
  "parameterized": {
    "parameterized_sql_snippet": "sales.purchaseMethod = '$1'",
    "parameterized_intent": "purchase method is $1"
  }
}
```

### Example (Nested Tag Predicate)

```json
{
  "sql_snippet": "items.tags = 'office'",
  "intent": "office supplies tag is exact string 'office'",
  "manifest": "office supplies tag",
  "parameterized": {
    "parameterized_sql_snippet": "items.tags = '$1'",
    "parameterized_intent": "items tag $1"
  }
}
```

## Best Practices & NoSQL Caveats

*   **Field Qualification**: Qualify fields using collection or subdocument path syntax (e.g., `sales.purchaseMethod`, `items.tags`, `customer.email`).
*   **String Formatting**: Explicitly capture non-hyphenated string conventions (e.g. `'In store'` instead of `'In-store'`) or tag aliases.
*   **Metric Formulas**: Provide operational snippets for NoSQL calculations:
    *   `sales.totalSales = SUM(items.price * items.quantity)`
    *   `sales.totalSalesVolume = SUM(items.quantity)`
