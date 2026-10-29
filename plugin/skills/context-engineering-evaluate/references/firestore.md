## Firestore (MongoDB Compatibility / MQL)

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: firestore`)
- Google Cloud Project ID (`project_id` or `project`)
- Database ID (`database_id` or `database`, e.g., `(default)`)

**Optional properties from `## Active Database` in `experiment_state.md`:**
- `**Table Ids**` (e.g., `- **Table Ids**: ["orders", "products", "customers"]`) — when present, `generate_evalbench_configs` sets `firestore_reference.database_reference.collection_ids` in `model_config.yaml` so QueryData scopes schema discovery to the active Firestore collection(s).

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: mongodb
dialect: mongodb
database_name: <database_id>
database_path: ""
firestore_database: projects/<project_id>/databases/<database_id>
max_executions_per_minute: 120
```

**EvalBench Model Config Spec (`model_config.yaml`):**

```yaml
generator: query_data_api
project_id: <project_id>
location: global
use_rest_api: true
context:
  datasource_references:
    firestore_reference:
      database_reference:
        project_id: <project_id>
        database_id: <database_id>
        collection_ids:
          - <collection_1>
          - <collection_2>
      agent_context_reference:
        context_set_id: <context_set_id>
```
