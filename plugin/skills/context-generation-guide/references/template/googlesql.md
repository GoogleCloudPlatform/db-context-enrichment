# Spanner (GoogleSQL) Template Generation Reference

This reference provides best practices and ideal output definitions for generating Templates in Spanner (GoogleSQL).

## Concepts

Templates map full natural language questions to full SQL queries. They are used to teach the system overarching operational logic.

## Parameterization

Values in the SQL/GQL query and the intent must be replaced with positional parameters represented by `?`, according to the [Phrase Extraction and Parameterization Guidelines](../phrase_extraction/guidelines.md).

### Example 1: Relational GoogleSQL

**Input**:
*   **Question**: "How many accounts are in London?"
*   **SQL**: `SELECT count(*) FROM account WHERE city = 'London'`
*   **Intent**: "How many accounts are in London?"

**Generated Output** (Conceptual):
```json
{
  "nl_query": "How many accounts are in London?",
  "sql": "SELECT count(*) FROM account WHERE city = 'London'",
  "intent": "How many accounts are in London?",
  "manifest": "How many accounts are in a given city?",
  "parameterized": {
    "parameterized_sql": "SELECT count(*) FROM account WHERE city = ?",
    "parameterized_intent": "How many accounts are in ?"
  }
}
```

### Example 2: Spanner Graph (Pure GQL)

Spanner Graph queries using `GRAPH <graph_name> MATCH ...` are supported under the Spanner GoogleSQL dialect.

**Input**:
*   **Question**: "Find all experts working at Google."
*   **SQL**: `GRAPH ResearchGraph MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE c.name_normalised = 'Google' RETURN e.name`
*   **Intent**: "Find all experts working at Google."

**Generated Output** (Conceptual):
```json
{
  "nl_query": "Find all experts working at Google.",
  "sql": "GRAPH ResearchGraph MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE c.name_normalised = 'Google' RETURN e.name",
  "intent": "Find all experts working at Google.",
  "manifest": "Find all experts working at a given company.",
  "parameterized": {
    "parameterized_sql": "GRAPH ResearchGraph MATCH (e:Expert)-[:HAS_EMPLOYMENT]->(emp:EmploymentRecord)-[:AT_COMPANY]->(c:Company) WHERE c.name_normalised = ? RETURN e.name",
    "parameterized_intent": "Find all experts working at ?"
  }
}
```

### Example 3: Spanner Graph (GoogleSQL with GRAPH_TABLE)

**Input**:
*   **Question**: "List companies and the count of their associated products."
*   **SQL**: `SELECT c.name_normalised, g.product_count FROM Company c JOIN GRAPH_TABLE(ResearchGraph MATCH (comp:Company)-[:OWNS]->(p:Product) WHERE comp.id = c.id COLUMNS (COUNT(p.id) AS product_count)) g ON TRUE`
*   **Intent**: "List companies and the count of their associated products."

**Generated Output** (Conceptual):
```json
{
  "nl_query": "List companies and the count of their associated products.",
  "sql": "SELECT c.name_normalised, g.product_count FROM Company c JOIN GRAPH_TABLE(ResearchGraph MATCH (comp:Company)-[:OWNS]->(p:Product) WHERE comp.id = c.id COLUMNS (COUNT(p.id) AS product_count)) g ON TRUE",
  "intent": "List companies and the count of their associated products.",
  "manifest": "List companies and the count of their associated products.",
  "parameterized": {
    "parameterized_sql": "SELECT c.name_normalised, g.product_count FROM Company c JOIN GRAPH_TABLE(ResearchGraph MATCH (comp:Company)-[:OWNS]->(p:Product) WHERE comp.id = c.id COLUMNS (COUNT(p.id) AS product_count)) g ON TRUE",
    "parameterized_intent": "List companies and the count of their associated products."
  }
}
```

## Best Practices

*   Provide complete, executable SQL or GQL queries.
*   Ensure the SQL/GQL follows Spanner (GoogleSQL) syntax.
*   For Spanner Graph, you can use pure GQL (`GRAPH <graph_name> MATCH ...`) or GoogleSQL with `GRAPH_TABLE(<graph_name> MATCH ...)`.
*   The intent should accurately describe what the query does.
