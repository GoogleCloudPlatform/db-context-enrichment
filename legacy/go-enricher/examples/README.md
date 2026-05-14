# Demo Database for Context Enrichment

In the `example` folder, you'll find a sample PostgreSQL database intentionally designed with ambiguous schema elements, including vague table and column names.

Without additional context, generating accurate SQL queries for natural language questions against this database becomes challenging.

## Demo Database Schema Overview

The demo schema contains three tables: `users`, `p`, and `orders`.

Several table and column names lack clarity. For instance, `p` represents the product table, but its columns are all abbreviated (e.g., `w` for weight).

## Leveraging External Knowledge

The folder also includes a sample "BI Guide," serving as a form of external knowledge typical for onboarding new Business Intelligence team members. This document contains implicit hints and context necessary for effectively using the dataset.

By applying a context enrichment tool, we can generate descriptive comments that augment the database schema. This enriched information not only serves as documentation for database users but also improves the accuracy of text-to-SQL systems.

## Demo Text-to-SQL Examples

Below are a few text-to-SQL examples that you can test using the Cloud SQL Studio Gemini SQL generation feature.

### Question 1

Question: How many users are in the state of California?

Expected answer:
```sql
SELECT COUNT(*) FROM "users" WHERE "state" = 'CA';
```

The `state` column uses abbreviations (e.g., 'CA' for California). Without context enrichment, inferring the correct abbreviation would be difficult.

### Question 2

Question: How many products weigh more than 1 kg?

Expected answer:
```sql
SELECT COUNT(*) FROM "p" WHERE "w" > 1000;
```

Here, both the table name (`p` for products) and the column name (`w` for weight) are non-descriptive. Furthermore, the weight is stored in grams, requiring a conversion to answer the question posed in kilograms.

### Question 3

Question: Provide a list of user names, emails, and their billing addresses, using the shipping address if the billing address is missing.

Expected answer:
```sql
SELECT "users"."name", "users"."email", COALESCE("users"."billing_address", "users"."shipping_address") AS "billing_statement_address" FROM "users";
```

This question's complexity lies in the requirement to default to the user's shipping address when the billing address is unavailable—a business rule typically found in external documentation like the provided BI Guide. Without this crucial context, a text-to-SQL system would likely fail to generate the correct query.
