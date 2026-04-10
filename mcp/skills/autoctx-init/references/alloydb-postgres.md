## AlloyDB Postgres

**Required Information:**
- Data Source Name (e.g., `my-alloydb`)
- Google Cloud Project ID
- Region
- Cluster ID
- Instance ID
- Database Name
- Database User (Optional, omit for ADC / IAM Auth)
- Database Password (Optional, omit for ADC / IAM Auth)

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
# user: <user>         # Optional (Omit for ADC / IAM Auth)
# password: <password> # Optional (Omit for ADC / IAM Auth)
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

> [!NOTE]
> If `user` and `password` are omitted, the system will attempt to use Application Default Credentials (ADC) and IAM Authentication to connect to the database.

