## Cloud SQL Postgres

**Required properties from the `kind: source` block in `autoctx_config.yaml`:**
- Source Type (`type: cloud-sql-postgres`)
- Google Cloud Project ID (`project_id`)
- Region (`region`)
- Instance ID (`instance_id`)
- Database Name (`database_name`)
- Database User (`user`)
- Database Password (`password`)

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: postgres
dialect: postgres
database_name: <database_name>
database_path: <project_id>:<region>:<instance_id>
max_executions_per_minute: 180
user_name: <user>
password: <password>
```
