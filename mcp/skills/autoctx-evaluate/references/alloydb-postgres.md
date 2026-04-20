## AlloyDB Postgres

**Required properties from the `kind: source` block in `tools.yaml`:**
- Source Type (`type: alloydb-postgres`)
- Google Cloud Project ID (`project_id`)
- Region (`region`)
- Cluster ID (`cluster_id`)
- Instance ID (`instance_id`)
- Database Name (`database_name`)
- Database User (`user`)
- Database Password (`password`)

**EvalBench Database Config Spec (`db_config.yaml`):**

```yaml
db_type: alloydb
dialect: postgres
database_name: <database_name>
database_path: projects/<project_id>/locations/<region>/clusters/<cluster_id>/instances/<instance_id>
max_executions_per_minute: 180
user_name: <user>
password: <password>
```
