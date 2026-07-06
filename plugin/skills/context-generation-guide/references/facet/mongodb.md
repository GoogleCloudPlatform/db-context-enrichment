# MongoDB (MQL / Firestore Enterprise Edition) Facet Generation Reference

This reference provides best practices and ideal output definitions for generating Facets in MongoDB MQL (`firestore_mql`) and Firestore Enterprise Edition with MongoDB Compatible API.

## Concepts

Facets are modular, reusable NoSQL filter fragments or field-value predicates (such as `$match` stages or nested document predicates). They link natural language terminology to specific NoSQL query conditions.

## Parameterization

Values in the NoSQL snippet and intent are parameterized using positional placeholders (e.g. `$1`), according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example (DART Ecommerce Dataset - Payment Method)

**Input**:
*   **Term / Concept**: "Credit card payment method"
*   **NoSQL Snippet**: `orders.payment_method = 'credit_card'`
*   **Intent**: "Credit card payment method string literal credit_card"

**Generated Output**:
```json
{
  "sql_snippet": "orders.payment_method = 'credit_card'",
  "intent": "credit card payment method is literal string 'credit_card'",
  "manifest": "Credit card payment method",
  "parameterized": {
    "parameterized_sql_snippet": "orders.payment_method = '$1'",
    "parameterized_intent": "payment method is $1"
  }
}
```

### Example (DART Ecommerce Dataset - Order Status)

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

## Best Practices & NoSQL Caveats

*   **Field Qualification**: Qualify fields using collection or subdocument path syntax (e.g., `orders.payment_method`, `orders.status`, `products.category`).
*   **String Formatting**: Explicitly capture specific stored string conventions (e.g. `'credit_card'` instead of `'Credit Card'`).
*   **Metric Formulas**: Provide operational snippets for NoSQL calculations:
    *   `orders.totalRevenue = SUM(orders.total_amount)`
    *   `products.totalSales = SUM(items.price * items.quantity)`
