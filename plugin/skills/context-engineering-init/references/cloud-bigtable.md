## Cloud Bigtable

**Required Information:**
- Data Source Name (e.g., `my-bigtable-db`)
- Google Cloud Project ID
- Instance ID

**Template:**

```yaml
kind: source
name: <data_source_name>
type: bigtable
project: <project_id>
instance: <instance_id>
---
kind: tool
name: <data_source_name>-list-schemas
type: bigtable-list-schemas
source: <data_source_name>
description: |
  Use this tool to list tables and their column families in the <data_source_name> Bigtable instance.

  Progressive Schema Discovery (Recommended):
  1) Fetch structure first (output_format='simple'),
  2) Go deep on specific parts if interested,
  3) Use batching if info is too large.

  Behavior:
  - Omit 'table_names' to fetch all tables.
  - Omit 'output_format' for detailed schema (default).
---
kind: tool
name: <data_source_name>-execute-sql
type: bigtable-sql
source: <data_source_name>
description: Use this tool to execute BTQL queries against the <data_source_name> Bigtable instance.
statement: "{{.sql}}"
templateParameters:
  - name: sql
    type: string
    description: BTQL query to execute
```
