## Spanner PostgreSQL

**Required Information:**
- Data Source Name (e.g., `my-spanner-db`)
- Google Cloud Project ID
- Instance ID
- Database Name
- Dialect

**Template (Spanner PostgreSQL):**

```yaml
kind: source
name: <data_source_name>
type: spanner
project: <project_id>
instance: <instance_id>
database: <database_name>
dialect: POSTGRESQL
---
kind: tool
name: <data_source_name>-list-schemas
type: spanner-list-tables
source: <data_source_name>
description: |
  Use this tool to list tables and their schemas in the <data_source_name> database.

  Progressive Schema Discovery (Recommended):
  1) Fetch structure first (output_format='simple'),
  2) Go deep on specific parts if interested,
  3) Use batching if info is too large.

  Scope:
  - The tool can fetch system/extension schemas. Agents should ignore them and focus on user data.
  - Introspects Spanner PostgreSQL information_schema scoped to schemas such as 'public'.

  Behavior:
  - Omit 'table_names' to fetch all tables.
  - Omit 'output_format' for detailed schema (default).
---
kind: tool
name: <data_source_name>-execute-sql
type: spanner-execute-sql
source: <data_source_name>
description: Use this tool to execute Spanner PostgreSQL statements against the <data_source_name> database.
```

### Dialect Verification (CLI)

If the user specifies a Spanner database but does not indicate whether it uses GoogleSQL or PostgreSQL dialect, the agent can verify the dialect using the `gcloud` CLI:

```bash
gcloud spanner databases describe <database_name> --instance=<instance_id> --project=<project_id> --format="value(databaseDialect)"
```
- Returns `POSTGRESQL` for Spanner PostgreSQL databases.
- Returns `GOOGLE_STANDARD_SQL` (or empty/null for older instances) for Spanner GoogleSQL databases.

If the CLI is not accessible, explicitly ask the user to confirm the dialect.

