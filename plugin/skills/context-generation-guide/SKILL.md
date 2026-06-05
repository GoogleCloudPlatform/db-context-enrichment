---
name: context-generation-guide
description: Guidelines and best practices for generating context items (Templates, Facets, Value Searches). Use this skill whenever the user asks to create, author, or generate context for database enrichment, or asks for examples and instructions on how to write templates, facets, or value searches. It helps bridge the gap between LLMs and structured databases.
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
3.  **Select Dialect Reference**: Identify the target database dialect (PostgreSQL, GoogleSQL, or MySQL) and consult the corresponding file in `references/` for specific syntax and patterns.
4.  **Parameterize**: Follow the [Phrase Extraction and Parameterization Guidelines](references/phrase_extraction/guidelines.md) to generalize the values.
5.  **Format Output**: Construct the final JSON object according to the examples in the reference files.
6.  **Save Context**: Use the appropriate MCP tool (e.g., `mutate_context_set`) to save or update the context set.

Note: Use the `mutate_context_set` tool for all ContextSet changes. It supports granular additions, updates, and deletions of ContextSet items without replacing the whole file. Pass mutation payloads directly — the tool handles all file I/O internally, so the agent should not read the target file beforehand.

## Context Type Definitions

### 1. Templates
A **Template** represents a complete mapping between a natural language query and an executable SQL query. It is composed of:
*   **Natural Language Question**: An example question asking for specific data.
*   **SQL Query**: The exact SQL query that correctly answers the question.
*   **Intent**: The specific goal of the query.
*   **Manifest**: A generalized description of the template's purpose.
*   **Parameterized Form**: The SQL and intent with specific values replaced by placeholders (e.g., `$1`).

```json
{
    "templates": [
        {
            "nl_query": "How many accounts are in London?",
            "sql": "SELECT count(*) FROM account WHERE city = 'London'",
            "intent": "How many accounts are in London?",
            "manifest": "How many accounts are in a given city?",
            "parameterized": {
                "parameterized_sql": "SELECT count(*) FROM account WHERE city = $1",
                "parameterized_intent": "How many accounts are in $1?"
            }
        }
    ]
}
```


### 2. Facets
A **Facet** is a modular SQL fragment representing a specific filter or condition. It is composed of:
*   **SQL Snippet**: The SQL fragment (usually a boolean expression or part of a WHERE clause). Every column reference **must** be qualified with its table name (e.g., `table.column`) so the fragment is unambiguous when injected into a query that joins multiple tables. Schema/database prefixes are not required.
*   **Intent**: The natural language expression corresponding to the snippet.
*   **Manifest**: A generalized description of the facet.
*   **Parameterized Form**: The SQL snippet and intent with specific values replaced by placeholders.

```json
{
    "facets": [
        {
            "sql_snippet": "rating > 4.5",
            "intent": "highly rated products (above 4.5)",
            "manifest": "highly rated products (above a given number)",
            "parameterized": {
                "parameterized_sql_snippet": "rating > $1",
                "parameterized_intent": "highly rated products (above $1)"
            }
        }
    ]
}
```

### 3. Value Searches
A **Value Search** defines how to look up values that might not match exactly. It requires:
*   **Target Concept**: The entity being searched (e.g., "City").
*   **Database Location**: The specific Table and Column containing the values.
*   **Match Strategy**: The function used for matching (e.g., Trigram, Semantic).
*   **Dialect-Specific Configuration**: Any specific columns or parameters required by the dialect.

```json
{
    "value_searches": [
        {
            "concept_type": "City",
            "query": "SELECT T.\"location\" AS value, 'users.location' AS columns, 'City' AS concept_type, fuzzy_distance(T.\"location\", $value) AS distance FROM \"users\" T WHERE fuzzy_match(T.\"location\", $value)",
            "description": "Fuzzy match for city in location column"
        }
    ]
}
```

## Best Practices

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

For specific SQL templates, examples, and performance recommendations, refer to the subdirectories in `references/`:

*   **Templates**:
    *   [PostgreSQL](references/template/postgresql.md)
    *   [Spanner (GoogleSQL)](references/template/googlesql.md)
    *   [MySQL](references/template/mysql.md)
*   **Facets**:
    *   [PostgreSQL](references/facet/postgresql.md)
    *   [Spanner (GoogleSQL)](references/facet/googlesql.md)
    *   [MySQL](references/facet/mysql.md)
*   **Value Searches**:
    *   [PostgreSQL](references/value_search/postgresql.md)
    *   [Spanner (GoogleSQL)](references/value_search/googlesql.md)
    *   [MySQL](references/value_search/mysql.md)
