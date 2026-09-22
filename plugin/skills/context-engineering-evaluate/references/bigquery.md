## BigQuery

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: bigquery`)
- Google Cloud Project ID (`project`)
- Dataset ID (`dataset`)

**Optional properties:**
- Dataset location (`location`, e.g. `US`, `EU`, `us-central1`): written to `db_config.yaml` and used only by EvalBench to execute queries.
- GDA API location (`region`): the location used for Gemini Data Analytics API calls in `model_config.yaml`. Defaults to `global`. This is independent of `location`; BigQuery multi-regions such as `US` are not valid GDA locations, so `location` is never used here.

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: bigquery
dialect: googlesql
database_name: <dataset_id>
database_path: projects/<project_id>/datasets/<dataset_id>
gcp_project_id: <project_id>
max_executions_per_minute: 100
location: <dataset_location>  # only if `location` is set
```
