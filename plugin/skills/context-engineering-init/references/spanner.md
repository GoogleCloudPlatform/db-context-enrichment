## Spanner

**Required Information:**
- Data Source Name (e.g., `my-spanner-db`)
- Google Cloud Project ID
- Instance ID
- Database Name
- *(Optional)* Property Graph Name (e.g., `ResearchGraph` for Spanner Graph workloads)

**Template (Standard Spanner):**

```yaml
kind: source
name: <data_source_name>
type: spanner
project: <project_id>
instance: <instance_id>
database: <database_name>
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
description: Use this tool to execute SQL statements against the <data_source_name> database.
```

**Template (Spanner Graph):**

If the database contains a property graph and the workload targets graph queries:

```yaml
kind: source
name: <data_source_name>
type: spanner
project: <project_id>
instance: <instance_id>
database: <database_name>
graph: <graph_name>
---
kind: tool
name: <data_source_name>-list-schemas
type: spanner-list-tables
source: <data_source_name>
description: Use this tool to list tables and schemas in the <data_source_name> database.
---
kind: tool
name: <data_source_name>-list-graphs
type: spanner-list-graphs
source: <data_source_name>
description: Use this tool to list property graphs and their node/edge schemas in the <data_source_name> database.
---
kind: tool
name: <data_source_name>-execute-sql
type: spanner-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL or GQL statements against the <data_source_name> database.
```
