# Firestore (MQL) Facet Generation Reference

This reference provides best practices, format definitions, and guidelines for authoring Facets in Firestore (MQL) and Firestore Enterprise Edition with MongoDB Compatible API.

## Concepts

Facets are modular, reusable NoSQL filter fragments, field-value predicates, or metric formulas. They link natural language terminology to specific NoSQL conditions or calculation rules.

---

## Formats: MQL JSON Predicates vs. Structured Query Expressions

In Firestore (MQL), `sql_snippet` supports two distinct representation formats depending on the nature of the facet:

| Format | Syntax Example | Recommended Use Case |
|---|---|---|
| **MQL JSON Predicate** | `{ "payment_method": "credit_card" }`<br>`{ "rating": { "$gt": 4.5 } }` | Direct document filters, query document conditions, array matching (`$elemMatch`), and MQL operators (`$in`, `$gt`, `$exists`) that drop into `$match` pipeline stages or `find()` queries. |
| **Structured Query Expression** | `orders.payment_method = 'credit_card'`<br>`orders.totalRevenue = SUM(orders.total_amount)` | High-level declarative business definitions, simple equality conditions, and metric/aggregation calculation formulas. |

---

## 1. MQL JSON Predicate Format (Recommended for Filter Predicates)

Use the MQL JSON object format when defining direct document filtering conditions.

### Example: Exact Field Filter
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

### Example: Range / Operator Filter
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

### Example: Nested Array Element Match
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

---

## 2. Structured Query Expression Format (Recommended for Formulas & Definitions)

Use structured query expressions when defining high-level business definitions, aliases, or metric calculation formulas that span multiple fields.

### Example: Status Expression
```json
{
  "sql_snippet": "orders.status = 'completed'",
  "intent": "completed order status is exact string 'completed'",
  "manifest": "completed order status filter",
  "parameterized": {
    "parameterized_sql_snippet": "orders.status = '$1'",
    "parameterized_intent": "order status is $1"
  }
}
```

### Example: Metric Calculation Formula
```json
{
  "sql_snippet": "orders.totalRevenue = SUM(orders.total_amount)",
  "intent": "total revenue formula for orders",
  "manifest": "orders total revenue formula",
  "parameterized": {
    "parameterized_sql_snippet": "orders.totalRevenue = SUM(orders.total_amount)",
    "parameterized_intent": "orders total revenue formula"
  }
}
```

---

## Best Practices & NoSQL Guidelines

*   **When to Use MQL JSON Object**: Choose MQL JSON format when the intent maps to an explicit MQL query filter stage or uses NoSQL operators (`$gt`, `$elemMatch`, `$in`, `$regex`).
*   **When to Use Structured Query Expression**: Choose structured expressions for metric definitions, formulas (`SUM(...)`), or simple descriptive field mappings.
*   **Field Qualification**: Always qualify fields with their collection or nested subdocument path (e.g., `orders.payment_method`, `customer.address.city`).
*   **Case Sensitivity**: Match the exact case and spacing of values stored in the database (e.g. `'credit_card'`, `'In store'`).
*   **Parameterization**: Parameterize literal values using positional placeholders (`$1`, `$2`) according to the [Phrase Extraction Guidelines](../phrase_extraction/guidelines.md).
