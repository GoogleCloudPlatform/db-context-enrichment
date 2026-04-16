## Cloud SQL MySQL

**Required Information:**
- Data Source Name (e.g., `my-mysql-db`)
- Google Cloud Project ID
- Region
- Instance Name
- Database Name

**Template:**

```yaml
kind: source
name: <data_source_name>
type: cloud-sql-mysql
project: <project_id>
region: <region>
instance: <instance_name>
database: <database_name>
---
kind: tool
name: <data_source_name>-list-schemas
type: mysql-list-tables
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
type: mysql-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL statements against the <data_source_name> database.
```



