---
name: context-generation-guide
description: Guidelines and best practices for generating context items (Templates, Facets, Value Searches). Use this skill whenever the user asks to create, author, or generate context for database enrichment, or asks for examples and instructions on how to write templates, facets, or value searches. It helps bridge the gap between LLMs and structured databases. For running the automated generation, evaluation, and tuning lifecycle, see the context-engineering-workflow skill.
---

# Context Generation Guide Skill


This skill provides the agent with the necessary information, concepts, and best practices to generate high-quality context items for the "Context Engineering Agent". This context bridges the gap between LLMs and structured databases, enabling accurate Natural Language to SQL generation.

## Overview

Context generation allows you to create specific, high-value items in three forms:

1.  **Templates**: End-to-end mappings linking a natural language query to a complete, runnable SQL query. They teach the system overarching operational logic, table join infrastructures, and broad business rules.
2.  **Facets**: Reusable, modular SQL fragments (like a `WHERE` clause or specialized join). They are dynamically injected filters linked to specific vocabulary or terminology.
3.  **Value Searches**: Specialized queries used when a value in the natural language query does not perfectly match the stored value in the database. They employ mapping functions to find candidate values.

## Workflow

When asked to generate context items:
1.  **Identify the Type**: Determine if the user wants to create a Template, Facet, or Value Search.
2.  **Gather Information**: Ensure you have all the required information for the chosen context type as described in the "Context Type Definitions" section below. If information is missing, try to explore the database to find it or ask the user for clarification.
3.  **Select Dialect Reference**: Identify the target database dialect (PostgreSQL, GoogleSQL, MySQL, or Firestore NoSQL MQL) and consult the corresponding file in `references/` for specific syntax and patterns.
4.  **Parameterize**: Follow the [Phrase Extraction and Parameterization Guidelines](references/phrase_extraction/guidelines.md) to generalize the values.
5.  **Format Output**: Construct the final JSON object according to the examples in the reference files.
6.  **Save Context**: Use the appropriate MCP tool (e.g., `mutate_context_set`) to save or update the context set.

Note: Use the `mutate_context_set` tool for all ContextSet changes. It supports granular additions, updates, and deletions of ContextSet items without replacing the whole file. Pass mutation payloads directly — the tool handles all file I/O internally, so the agent should not read the target file beforehand.

## Context Type Definitions & Rationale

A `ContextSet` is the central artifact managed by the Context Engineering Agent, containing structured knowledge to help the Gemini Data Analytics API understand your database and business logic. 

The following are the currently supported context types:

---

## 1. Blueprints for Predictable SQL Generation: Templates & Facets

**Templates** and **Facets** act as structural **blueprints** that use the pattern of ML tool selection and tool calling to constrain SQL generation. By providing the model with these pre-defined patterns, you ensure that generated queries are highly predictable, structurally sound, and adhere to established database join structures.

### Templates
* **Purpose**: A blueprint for a complete query lifecycle. It maps a representative natural language query to an executable SQL statement and a declarative intent, teaching the model the overarching operational logic and join paths for a common query pattern.
* **Parameterization**: Templates are generalized by replacing literal values in both the intent and SQL with placeholders (e.g., `$1`, `$2`) to match query variations.
* **Schema Layout**:
```json
{
  "templates": [
    {
      "nl_query": "How many accounts are in London?",
      "sql": "SELECT count(*) FROM account WHERE account.city = 'London'",
      "intent": "How many accounts are in London?",
      "manifest": "How many accounts are in a given city?",
      "parameterized": {
        "parameterized_sql": "SELECT count(*) FROM account WHERE account.city = $1",
        "parameterized_intent": "How many accounts are in $1?"
      }
    }
  ]
}
```

### Facets
* **Purpose**: A modular blueprint fragment representing a specific condition, filter, or specialized join predicate. They are dynamically injected filters linked to specific vocabulary, allowing the model to compose complex queries from smaller, validated fragments.
* **Qualification Rule**: To prevent syntax and ambiguity errors during multi-table joins, **every column reference in a facet MUST be qualified with its table name** (e.g., `table_name.column_name`).
* **Schema Layout**:
```json
{
  "facets": [
    {
      "sql_snippet": "products.rating > 4.5",
      "intent": "highly rated products (above 4.5)",
      "manifest": "highly rated products (above a given number)",
      "parameterized": {
        "parameterized_sql_snippet": "products.rating > $1",
        "parameterized_intent": "highly rated products (above $1)"
      }
    }
  ]
}
```

---

## 2. Resolving the Value Linking Problem: Value Search Queries

When executing blueprint-driven SQL generation, the model inevitably runs into the **value linking problem**—where values in a user's natural language query (e.g., "Heathrow", "Lndn", "active") do not match the exact spelling, case, or formatting of stored records in the database (e.g., "London Heathrow", "London", "ACTIVE_STATUS"). 

**Value Search Queries** are the developer-defined mechanism used to resolve the value linking problem, mapping user-supplied terms to their precise schema locations and database records using exact, trigram, or semantic match functions.

* **Schema Layout**:
```json
{
  "value_searches": [
    {
      "query": "SELECT T.\"name\" AS value, 'airports.name' AS columns, 'Airport Name' AS concept_type, (T.\"name\" <-> $value::text) AS distance, '{}'::text AS context FROM \"airports\" T WHERE T.\"name\" % $value::text",
      "concept_type": "Airport Name",
      "description": "Fuzzy match using standard trigram for partial airport names"
    }
  ]
}
```

## 

### General
*   **Focus on Quality**: Provide accurate and representative examples.
*   **Avoid Redundancy**: Don't create duplicate templates or facets for the same logic.

### Templates & Facets
*   Ensure SQL is valid for the target dialect.
*   Intents should be clear and descriptive.
*   **Use Parameters**: parameterize values in the SQL and intent according to the [Phrase Extraction and Parameterization Guidelines](references/phrase_extraction/guidelines.md). This is necessary to generalize the context items so they can match variations of user queries.

### Facets
*   **Always qualify every column reference with its table name** (`table.column`) in both the literal and parameterized SQL snippets. A facet is injected into a larger query that may join multiple tables, so unqualified column names risk ambiguity errors or silently binding to the wrong column. Do not use aliases — the surrounding query controls them.

### Value Searches
*   Choose the appropriate match function based on the column content and performance requirements.
*   Refer to dialect-specific references for performance optimizations (e.g., indices).

## Shared Guidelines

*   [Phrase Extraction and Parameterization](references/phrase_extraction/guidelines.md): Instructions for extracting value phrases and replacing them with placeholders.

## Dialect References

For specific SQL/NoSQL templates, examples, and performance recommendations, refer to the subdirectories in `references/`:

*   **Templates**:
    *   [PostgreSQL](references/template/postgresql.md)
    *   [Spanner (GoogleSQL)](references/template/googlesql.md)
    *   [MySQL](references/template/mysql.md)
    *   [Firestore (NoSQL MQL)](references/template/firestore.md)
*   **Facets**:
    *   [PostgreSQL](references/facet/postgresql.md)
    *   [Spanner (GoogleSQL)](references/facet/googlesql.md)
    *   [MySQL](references/facet/mysql.md)
    *   [Firestore (NoSQL MQL)](references/facet/firestore.md)
*   **Value Searches**:
    *   [PostgreSQL](references/value_search/postgresql.md)
    *   [Spanner (GoogleSQL)](references/value_search/googlesql.md)
    *   [MySQL](references/value_search/mysql.md)
    *   [Firestore (NoSQL MQL)](references/value_search/firestore.md)

