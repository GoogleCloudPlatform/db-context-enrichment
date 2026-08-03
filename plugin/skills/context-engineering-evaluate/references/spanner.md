## Spanner

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: spanner`)
- Google Cloud Project ID (`project_id`)
- Instance ID (`instance_id`)
- Database Name (`database_name`)
- *(Optional)* Property Graph IDs (`graph_ids`)

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

**EvalBench Model Config Spec (`model_config.yaml`):**

For Spanner Graph (when `graph_ids: [<graph_name>]` is configured in `tools.yaml`), `model_config.yaml` includes `graph_ids` and `use_rest_api: true`:

```yaml
generator: query_data_api
project_id: <project_id>
location: global
use_rest_api: true
context:
  datasource_references:
    spanner_reference:
      database_reference:
        engine: GOOGLE_SQL
        project_id: <project_id>
        instance_id: <instance_id>
        database_id: <database_name>
        graph_ids:
          - <graph_name>
      agent_context_reference:
        context_set_id: <context_set_id>
```
