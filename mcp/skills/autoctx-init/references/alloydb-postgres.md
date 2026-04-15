## AlloyDB Postgres

**Required Information:**
- Data Source Name (e.g., `my-alloydb`)
- Google Cloud Project ID
- Region
- Cluster ID
- Instance ID
- Database Name

**Template:**

```yaml
kind: source
name: <data_source_name>
type: alloydb-postgres
project: <project_id>
region: <region>
cluster: <cluster_id>
instance: <instance_id>
database: <database_name>
---
kind: tool
name: <data_source_name>-list-schemas
type: postgres-list-tables
source: <data_source_name>
description: |
  Use this tool to list tables and their schemas in the <data_source_name> database. Follow Progressive Schema Discovery
  1) Fetch structure first (output_format='simple'),
  2) Go deep on specific parts if interested,
  3) Use batching if info is too large.
  Focus on user data by ignoring system/extension schemas.
---
kind: tool
name: <data_source_name>-execute-sql
type: postgres-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL statements against the <data_source_name> database.
```



