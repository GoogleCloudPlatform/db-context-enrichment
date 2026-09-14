## Cloud Bigtable

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: bigtable`)
- Google Cloud Project ID (`project_id`)
- Instance ID (`instance_id`)

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: bigtable
dialect: bigtable
database_name: <instance_id>
database_path: projects/<project_id>/instances/<instance_id>
instance_id: <instance_id>
gcp_project_id: <project_id>
max_executions_per_minute: 100
```
