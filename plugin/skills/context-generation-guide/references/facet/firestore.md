# Firestore (MQL) Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in Firestore (MQL) and Firestore Enterprise Edition with MongoDB Compatible API.

## Concepts

Facets in Firestore (MQL) are modular, reusable NoSQL filter fragments and document field-value predicates. They link natural language terminology directly to MQL query filter documents that drop into `$match` pipeline stages or `db.collection.find(...)` queries.

In Firestore (MQL), `sql_snippet` is written in **MQL JSON Predicate Format** (e.g. `{ "orders.payment_method": "credit_card" }`, `{ "orders.status": "completed" }`, `{ "products.rating": { "$gt": 4.5 } }`).

---

## Parameterization

Values in the MQL JSON snippet and intent are parameterized using positional placeholders (e.g. `$1`, `$2`), according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

---

## Examples

### 1. Exact Field Filter (Payment Method)
```json
{
  "sql_snippet": "{ \"orders.payment_method\": \"credit_card\" }",
  "intent": "credit card payment method is literal string 'credit_card'",
  "manifest": "Credit card payment method filter",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"orders.payment_method\": \"$1\" }",
    "parameterized_intent": "payment method is $1"
  }
}
```

### 2. Status Filter (Completed Orders)
```json
{
  "sql_snippet": "{ \"orders.status\": \"completed\" }",
  "intent": "completed order status is exact string 'completed'",
  "manifest": "completed order status filter",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"orders.status\": \"$1\" }",
    "parameterized_intent": "order status is $1"
  }
}
```

### 3. Range / Comparison Filter (Numeric Threshold)
```json
{
  "sql_snippet": "{ \"products.rating\": { \"$gt\": 4.5 } }",
  "intent": "highly rated products (rating above 4.5)",
  "manifest": "highly rated products filter",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"products.rating\": { \"$gt\": $1 } }",
    "parameterized_intent": "products with rating above $1"
  }
}
```

### 4. Set Membership Filter ($in)
```json
{
  "sql_snippet": "{ \"orders.status\": { \"$in\": [\"active\", \"pending\"] } }",
  "intent": "active or pending order status",
  "manifest": "active or pending order status filter",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"orders.status\": { \"$in\": [$1] } }",
    "parameterized_intent": "order status in $1"
  }
}
```

### 5. Nested Array Element Filter ($elemMatch)
```json
{
  "sql_snippet": "{ \"items\": { \"$elemMatch\": { \"name\": \"Desk\", \"price\": { \"$gte\": 100 } } } }",
  "intent": "orders containing Desk item with price at least 100",
  "manifest": "orders containing specific item above a price threshold",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"items\": { \"$elemMatch\": { \"name\": \"$1\", \"price\": { \"$gte\": $2 } } } }",
    "parameterized_intent": "orders containing $1 item with price at least $2"
  }
}
```

### 6. Subdocument Path Filter (Dot Notation)
```json
{
  "sql_snippet": "{ \"customer.satisfaction\": { \"$gte\": 4 } }",
  "intent": "satisfied customer with rating of 4 or higher",
  "manifest": "satisfied customer rating filter",
  "parameterized": {
    "parameterized_sql_snippet": "{ \"customer.satisfaction\": { \"$gte\": $1 } }",
    "parameterized_intent": "customer satisfaction rating of $1 or higher"
  }
}
```

---

## Best Practices & NoSQL Guidelines

*   **MQL JSON Format**: Always author `sql_snippet` using MQL JSON object filter format (`{ "field": value }` or `{ "field": { "$operator": value } }`) so the snippet cleanly composes into `$match` pipeline stages and `find()` queries.
*   **Field Qualification**: Always qualify fields with collection or subdocument path syntax (e.g., `orders.payment_method`, `customer.satisfaction`, `items.price`).
*   **Case & Value Sensitivity**: Match the exact case and formatting of stored values (e.g. `'credit_card'`, `'completed'`, `'In store'`).
*   **NoSQL Operators**: Leverage native MQL operators (`$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$elemMatch`, `$exists`, `$regex`) for non-trivial filters.
