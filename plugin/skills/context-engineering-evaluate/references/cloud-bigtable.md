## Cloud Bigtable

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: bigtable`)
- Google Cloud Project ID (`project_id` or `project`)
- Instance ID (`instance_id` or `instance`)

**Optional properties from `## Active Database` in `experiment_state.md`:**
- `**Table Ids**` (e.g., `- **Table Ids**: ["hotels", "hotels_view"]`) — when present, `generate_evalbench_configs` sets `bigtable_reference.database_reference.table_ids` in `model_config.yaml` so QueryData scopes schema discovery on multi-table Bigtable instances to the active table(s) / logical view(s).

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
