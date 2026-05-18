# Phrase Extraction and Parameterization Guidelines

This guide provides instructions for extracting value phrases (named entities) from natural language queries and parameterizing them in both the SQL and the intent. This process is crucial for creating generalized Templates and Facets.

## Phase 1: Value Phrase Extraction

Identify and extract specific values (named entities) from the natural language query literally. Do not perform spell checking or correction.

### Target Entity Types

Extract entities that fall into these categories:

*   `country`
*   `city`
*   `email_address`
*   `language`
*   `law`
*   `organization`
*   `person`
*   `product`
*   `sport or activity`
*   `work of art`
*   `date`
*   `time`
*   `number`
*   `currency`
*   `region`

**Example**:
Query: "Show me sales in London and Paris for 2025"
Extracted Phrases: `["London", "Paris", "2025"]`

## Phase 2: Parameterization

Replace the extracted value phrases with placeholders in both the SQL query and the intent string.

### 1. Placeholder Syntax

*   **PostgreSQL**: Use positional parameters like `$1`, `$2`, `$3`, etc.
*   **Spanner (GoogleSQL) & MySQL**: Use `?` for all parameters.

### 2. Processing Order (Critical)

Always process the extracted phrases in **descending order of length**. This ensures that longer, compound phrases are replaced before shorter substrings that might be contained within them (e.g., "New York" should be replaced before "York").

### 3. Replacement Rules

You must handle different combinations of how the value appears in the SQL and the intent (quoted vs. unquoted).

*   **Case 1: Quoted in SQL, Quoted in Intent**
    *   SQL: `... WHERE city = 'London'`
    *   Intent: "accounts in 'London'"
    *   Result (PostgreSQL): `... WHERE city = $1`, "accounts in $1"
*   **Case 2: Quoted in SQL, Unquoted in Intent**
    *   SQL: `... WHERE city = 'London'`
    *   Intent: "accounts in London"
    *   Result (PostgreSQL): `... WHERE city = $1`, "accounts in $1"
*   **Case 3: Unquoted in SQL, Quoted in Intent**
    *   SQL: `... WHERE age > 21`
    *   Intent: "users older than '21'"
    *   Result (PostgreSQL): `... WHERE age > $1`, "users older than $1"
*   **Case 4: Unquoted in SQL, Unquoted in Intent**
    *   SQL: `... WHERE age > 21`
    *   Intent: "users older than 21"
    *   Result (PostgreSQL): `... WHERE age > $1`, "users older than $1"

### 4. Negative Lookbehind

Avoid replacing phrases that are already part of a placeholder (e.g., do not replace `'foo'` if it is already `$1`).

## Example Walkthrough (PostgreSQL)

**Input**:
*   **NL Query**: "How many accounts are in London?"
*   **SQL**: `SELECT count(*) FROM account WHERE city = 'London'`
*   **Intent**: "How many accounts are in London?"

**Step 1: Extract**
*   Phrase: `"London"` (Type: city)

**Step 2: Parameterize**
*   Dialect: PostgreSQL (use `$1`)
*   Occurrence: Quoted in SQL (`'London'`), Unquoted in Intent (`London`).
*   Output:
    *   **Parameterized SQL**: `SELECT count(*) FROM account WHERE city = $1`
    *   **Parameterized Intent**: "How many accounts are in $1?"
    *   **Manifest**: "How many accounts are in a given city?" (Generalized description)
