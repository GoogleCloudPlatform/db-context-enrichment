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
2.  **Gather Information**: Ensure you have all the required information listed in the "Information Needed" section. If anything is missing, ask the user to provide it.
3.  **Select Dialect Reference**: Identify the target database dialect (PostgreSQL, GoogleSQL, or MySQL) and consult the corresponding file in `references/` for specific syntax and patterns.
4.  **Parameterize**: Follow the [Phrase Extraction and Parameterization Guidelines](references/phrase_extraction/guidelines.md) to generalize the values.
5.  **Format Output**: Construct the final JSON object according to the examples in the reference files.
6.  **Save Context**: Use the appropriate MCP tool (e.g., `mutate_context_set`) to save or update the context set.

## Information Needed

### 1. Templates
To generate a template, you need:
*   **Natural Language Question**: The question a user might ask.
*   **SQL Query**: The correct, executable SQL query to answer that question.
*   **Intent** (Optional): A description of what the query does. Defaults to the question if not provided.

### 2. Facets
To generate a facet, you need:
*   **SQL Snippet**: The reusable SQL fragment (e.g., `rating > 4.5`).
*   **Intent**: The description of the condition (e.g., "highly rated products (above 4.5)").

### 3. Value Searches
To generate a value search, you need:
*   **Table Name**: The table containing the data.
*   **Column Name**: The column containing the values to search.
*   **Concept Type**: A high-level description of the concept (e.g., "City").
*   **Match Function**: The algorithm to use (e.g., `EXACT_MATCH_STRINGS`, `TRIGRAM_STRING_MATCH`, `SEMANTIC_SIMILARITY_MATCH`).
*   **Dialect-Specific Parameters**: E.g., token columns for Spanner or embedding columns for MySQL.

## Best Practices

### General
*   **Focus on Quality**: Provide accurate and representative examples.
*   **Avoid Redundancy**: Don't create duplicate templates or facets for the same logic.
*   **Use Parameters**: Manually parameterize values in the SQL and intent according to the [Phrase Extraction and Parameterization Guidelines](references/phrase_extraction/guidelines.md). This is necessary to generalize the context items so they can match variations of user queries.

### Templates & Facets
*   Ensure SQL is valid for the target dialect.
*   Intents should be clear and descriptive.

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
