# Firestore (NoSQL MQL) Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in Firestore Native Mode and MongoDB MQL (`firestore_mql`).

## Concepts

Templates map full natural language questions to complete NoSQL MQL queries (`db.collection.find(...)` or `db.collection.aggregate(...)`). They teach the model overarching operational logic, aggregation pipeline stages, and document field filtering rules.

## Parameterization

Values in the NoSQL query and the intent are parameterized using positional placeholders (e.g. `$1`, `$2`), according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example

**Input**:
*   **Question**: "What are the total sales for 'In store' purchases at the Denver location?"
*   **NoSQL MQL**: `db.sales.aggregate([{ $match: { purchaseMethod: 'In store', storeLocation: 'Denver' } }, { $unwind: '$items' }, { $group: { _id: null, totalSales: { $sum: { $multiply: ['$items.price', '$items.quantity'] } } } }, { $project: { _id: 0, totalSales: 1 } }])`
*   **Intent**: "Total sales revenue for In store purchases at Denver location"

**Generated Output**:
```json
{
  "nl_query": "What are the total sales for 'In store' purchases at the Denver location?",
  "sql": "db.sales.aggregate([{ $match: { purchaseMethod: 'In store', storeLocation: 'Denver' } }, { $unwind: '$items' }, { $group: { _id: null, totalSales: { $sum: { $multiply: ['$items.price', '$items.quantity'] } } } }, { $project: { _id: 0, totalSales: 1 } }])",
  "intent": "Total sales revenue for In store purchases at Denver location",
  "manifest": "Total sales revenue for a purchase method at a given store location",
  "parameterized": {
    "parameterized_sql": "db.sales.aggregate([{ $match: { purchaseMethod: '$1', storeLocation: '$2' } }, { $unwind: '$items' }, { $group: { _id: null, totalSales: { $sum: { $multiply: ['$items.price', '$items.quantity'] } } } }, { $project: { _id: 0, totalSales: 1 } }])",
    "parameterized_intent": "Total sales revenue for purchaseMethod $1 at storeLocation $2"
  }
}
```

## Best Practices & NoSQL Caveats

*   **Syntax Format**: Always use standard MongoDB shell syntax: `db.<collection>.find(...)` or `db.<collection>.aggregate([...])`.
*   **Nested Field Dot Notation**: Reference embedded document fields using dot notation (e.g. `'customer.satisfaction'`, `'items.price'`).
*   **Array Unwinding**: Replace multi-table relational joins with `{ $unwind: "$items" }` stages when computing metrics over array elements.
*   **Exact Value Matching**: Ensure literal string values match database case and spacing (e.g., `'In store'` with space vs `'In-store'`, `'stationary'` vs `'stationery'`).
*   **Date Objects**: Use ISO timestamp dates: `ISODate('YYYY-MM-DDTHH:MM:SSZ')`.
