## Spanner

**Required Information:**
- Data Source Name (e.g., `my-spanner-db`)
- Google Cloud Project ID
- Instance ID
- Database Name
- **Optional Property Graphs (`graph_ids`)**: When collecting Spanner connection details, explicitly indicate to the user that property graphs (`graph_ids`) are **optional**. Ask if their database contains property graphs (e.g., `[InfrastructureGraph, LogisticsNet]`, `[ResearchGraph]`) and if they wish to include graph relationship queries in the context scope. If none are provided, omit `graph_ids:` for standard relational SQL.

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
graph_ids:
  - <graph_name>
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
