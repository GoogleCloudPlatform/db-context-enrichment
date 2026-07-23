## BigQuery

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: bigquery`)
- Google Cloud Project ID (`project`)
- Dataset ID (`dataset`)

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: bigquery
dialect: googlesql
database_name: <dataset_id>
database_path: projects/<project_id>/datasets/<dataset_id>
gcp_project_id: <project_id>
max_executions_per_minute: 100
```
