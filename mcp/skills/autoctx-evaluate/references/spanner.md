## Spanner

**Required properties from the `kind: source` block in `autoctx_config.yaml`:**
- Source Type (`type: spanner`)
- Google Cloud Project ID (`project_id`)
- Instance ID (`instance_id`)
- Database Name (`database_name`)

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: spanner
dialect: spanner_gsql
database_name: <database_name>
database_path: projects/<project_id>/instances/<instance_id>/databases/<database_name>
instance_id: <instance_id>
gcp_project_id: <project_id>
max_executions_per_minute: 100
```
