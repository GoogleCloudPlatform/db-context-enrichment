# Phrase Extraction, Manifest Generation, and Parameterization Guidelines

This guide provides instructions for extracting value phrases (named entities) from natural language queries, generating a generalized manifest, and parameterizing them in both the SQL and the intent. This process is crucial for creating generalized Templates and Facets.

The output of Phase 1 feeds both Phase 2 (manifest) and Phase 3 (parameterization) — extract once, then reuse the same phrase set for both downstream steps.

## Phase 1: Value Phrase Extraction

Identify and extract specific values (named entities) from the natural language query literally. Do not perform spell checking or correction.

Each extracted phrase is associated with exactly one entity type, which is used for manifest generation in Phase 2.

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
Extracted Phrases: `{"London": "city", "Paris": "city", "2025": "date"}`

## Phase 2: Manifest Generation

The manifest is a generalized, human-readable description of the intent where each concrete value phrase is replaced by `a given <type>`. It is derived from the **intent string**, not the SQL.

### Rules

1.  **Source**: Start from the intent string (verbatim).
2.  **Replacement Form**: Substitute each occurrence with the literal string `a given <type>` (e.g., `a given city`, `a given date`).
3.  **Processing Order**: Process phrases in **descending order of length** so longer compound phrases (e.g., `"New York"`) are replaced before any shorter substring they contain (e.g., `"York"`).
4.  **No Quoting Awareness**: Manifest generation does a literal string replacement on the intent. It does not distinguish between quoted and unquoted occurrences.

### Example

*   **Intent**: `"Show me sales in London and Paris for 2025"`
*   **Phrases**: `{"London": "city", "Paris": "city", "2025": "date"}`
*   **Manifest**: `"Show me sales in a given city and a given city for a given date"`

## Phase 3: Parameterization

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

**Step 2: Generate Manifest**
*   Primary type for `"London"` is `city`.
*   **Manifest**: `"How many accounts are in a given city?"`

**Step 3: Parameterize**
*   Dialect: PostgreSQL (use `$1`)
*   Occurrence: Quoted in SQL (`'London'`), Unquoted in Intent (`London`).
*   Output:
    *   **Parameterized SQL**: `SELECT count(*) FROM account WHERE city = $1`
    *   **Parameterized Intent**: `"How many accounts are in $1?"`
