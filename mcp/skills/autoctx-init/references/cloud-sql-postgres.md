## Cloud SQL Postgres

**Required Information:**
- Data Source Name (e.g., `my-postgres-db`)
- Google Cloud Project ID
- Region
- Instance Name
- Database Name

**Template:**

```yaml
kind: source
name: <data_source_name>
type: cloud-sql-postgres
project: <project_id>
region: <region>
instance: <instance_name>
database: <database_name>
---
kind: tool
name: <data_source_name>-list-schemas
type: postgres-list-tables
source: <data_source_name>
description: Use this tool to list all tables and their schemas in the <data_source_name> database.
---
kind: tool
name: <data_source_name>-execute-sql
type: postgres-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL statements against the <data_source_name> database.
```



