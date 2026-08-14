# MongoDB (MQL / Firestore Enterprise Edition) Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in MongoDB MQL (`firestore_mql`) and Firestore Enterprise Edition with MongoDB Compatible API.

## Concepts

Templates map full natural language questions to complete NoSQL MQL queries (`db.collection.find(...)` or `db.collection.aggregate(...)`). They teach the model overarching operational logic, aggregation pipeline stages, and document field filtering rules.

## Parameterization

Values in the NoSQL query and the intent are parameterized using positional placeholders (e.g. `$1`, `$2`), according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Question**: "What is the total revenue for completed orders?"
*   **NoSQL MQL**: `db.orders.aggregate([{ $match: { status: 'completed' } }, { $group: { _id: null, totalRevenue: { $sum: '$total_amount' } } }, { $project: { _id: 0, totalRevenue: 1 } }])`
*   **Intent**: "Total revenue for completed orders"

**Generated Output**:
```json
{
  "nl_query": "What is the total revenue for completed orders?",
  "sql": "db.orders.aggregate([{ $match: { status: 'completed' } }, { $group: { _id: null, totalRevenue: { $sum: '$total_amount' } } }, { $project: { _id: 0, totalRevenue: 1 } }])",
  "intent": "Total revenue for completed orders",
  "manifest": "Total revenue for orders with a given status",
  "parameterized": {
    "parameterized_sql": "db.orders.aggregate([{ $match: { status: '$1' } }, { $group: { _id: null, totalRevenue: { $sum: '$total_amount' } } }, { $project: { _id: 0, totalRevenue: 1 } }])",
    "parameterized_intent": "Total revenue for orders with status $1"
  }
}
```

## Best Practices & NoSQL Caveats

*   **Syntax Format**: Always use standard MongoDB shell syntax: `db.<collection>.find(...)` or `db.<collection>.aggregate([...])`.
*   **Nested Field Dot Notation**: Reference embedded document fields using dot notation (e.g. `'customer.email'`, `'items.price'`).
*   **Array Unwinding**: Replace multi-table relational joins with `{ $unwind: "$items" }` stages when computing metrics over array elements.
*   **Exact Value Matching**: Ensure literal string values match database case and formatting (e.g., `'credit_card'`, `'completed'`).
*   **Date Objects**: Use ISO timestamp dates: `ISODate('YYYY-MM-DDTHH:MM:SSZ')`.
