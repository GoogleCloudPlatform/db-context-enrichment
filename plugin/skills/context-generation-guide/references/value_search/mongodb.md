# MongoDB (MQL / Firestore Enterprise Edition) Value Search Generation Reference

This reference provides best practices and ideal output definitions for Value Search queries in MongoDB MQL (`firestore_mql`) and Firestore Enterprise Edition with MongoDB Compatible API.

## Concepts

Value Search queries map user-supplied terms in natural language queries (e.g. "black laptop", "electronics", "credit card") to stored field values in NoSQL document collections.

## Schema Layout (DART Ecommerce Dataset)

```json
{
  "value_searches": [
    {
      "query": "db.products.find({ name: { $regex: $value, $options: 'i' } }, { name: 1, _id: 0 })",
      "concept_type": "Product Name",
      "description": "Fuzzy case-insensitive search for product names in products collection"
    }
  ]
}
```

## Best Practices

*   Use `$regex` with options `'i'` for case-insensitive partial value matching on string fields and array tags.
*   Limit projected fields to only target value fields to maximize performance.
