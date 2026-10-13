## BigQuery

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: bigquery`)
- Google Cloud Project ID (`project`)
- Dataset ID (`allowedDatasets`, exactly one entry; the toolbox BigQuery source has no `dataset` field)

**Required properties from the experiment's `experiment_state.md`:**
- Table IDs (`Table Ids` under `## Active Database`, e.g. `- **Table Ids**: [orders, customers]`). The QueryData API requires at least one table reference, and `tools.yaml` has no place for it. `generate_evalbench_configs` locates `experiment_state.md` by walking up from `output_dir`, so the output directory must be inside the experiment's `hillclimb/` folder. If the bullet is missing, populate it from the schema listing before generating configs.

**Optional properties:**
- Dataset location (`location`, e.g. `US`, `EU`, `us-central1`): written to `db_config.yaml` and used only by EvalBench to execute queries. It is **not** used as the Gemini Data Analytics API location — BigQuery multi-regions such as `US` are not valid GDA locations — so `model_config.yaml` always uses `global` for BigQuery.

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
