# MongoDB (MQL / Firestore Native) Value Search Generation Reference

This reference provides best practices and ideal output definitions for Value Search queries in MongoDB MQL (`firestore_mql`) and Firestore Native Mode.

## Concepts

Value Search queries map user-supplied terms in natural language queries (e.g. "school stationary", "Denver", "online") to stored field values in NoSQL document collections.

## Schema Layout

```json
{
  "value_searches": [
    {
      "query": "db.sales.find({ 'items.tags': { $regex: $value, $options: 'i' } }, { 'items.tags': 1, _id: 0 })",
      "concept_type": "Product Tag Name",
      "description": "Fuzzy case-insensitive search for product tag names in sales collection items"
    }
  ]
}
```

## Best Practices

*   Use `$regex` with options `'i'` for case-insensitive partial value matching on string fields and array tags.
*   Limit projected fields to only target value fields to maximize performance.
