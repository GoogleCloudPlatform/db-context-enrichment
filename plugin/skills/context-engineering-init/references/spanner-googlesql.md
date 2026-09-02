## Spanner GoogleSQL

**Required Information:**
- Data Source Name (e.g., `my-spanner-db`)
- Google Cloud Project ID
- Instance ID
- Database Name
- Dialect: `GOOGLESQL` (optional in `tools.yaml`, defaults to GoogleSQL if omitted)

### Template: Spanner GoogleSQL Configuration

```yaml
kind: source
name: <data_source_name>
type: spanner
project: <project_id>
instance: <instance_id>
database: <database_name>
dialect: GOOGLESQL
---
kind: tool
name: <data_source_name>-list-graphs
type: spanner-list-graphs
source: <data_source_name>
description: |
  Use this tool to list property graphs and their node/edge schemas in the <data_source_name> database. Use this
  to inspect graph tables before relational tables.

  Progressive Schema Discovery (Recommended):
  1) Fetch structure first (output_format='simple'),
  2) Go deep on specific parts if interested,
  3) Use batching if info is too large.

  Scope:
  - The tool can fetch system/extension schemas. Agents should ignore them and focus on user data.

  Behavior:
  - Omit 'graph_names' to fetch all graphs.
  - Omit 'output_format' for detailed schema (default).

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

  Behavior:
  - Omit 'table_names' to fetch all tables.
  - Omit 'output_format' for detailed schema (default).
---
kind: tool
name: <data_source_name>-execute-sql
type: spanner-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL or GQL statements against the <data_source_name> database.
```

### Dialect Verification (CLI)

If the user specifies a Spanner database but does not indicate whether it uses GoogleSQL or PostgreSQL dialect, the agent can verify the dialect using the `gcloud` CLI:

```bash
gcloud spanner databases describe <database_name> --instance=<instance_id> --project=<project_id> --format="value(databaseDialect)"
```
- Returns `GOOGLE_STANDARD_SQL` (or empty/null for older instances) for Spanner GoogleSQL databases.
- Returns `POSTGRESQL` for Spanner PostgreSQL databases.

If the CLI is not accessible, explicitly ask the user to confirm the dialect.

