# Pluggable / Custom Database Engine Configuration

AutoCtx and EvalBench support pluggable database engines via a generic Service Provider Interface (SPI). This enables third-party, specialized, or internal database engines and model runners to be evaluated within the AutoCtx lifecycle without modifying core framework code.

## Defining a Pluggable Engine in `tools.yaml`

To configure a custom or pluggable engine, set `type: custom` (or supply explicit `connector_class` and `generator_class` attributes) on the source definition in `tools.yaml`:

```yaml
kind: source
name: my_custom_db
type: custom
dialect: googlesql           # SQL dialect (e.g., googlesql, postgres, sqlite, etc.)
connector_class: my_package.connectors.CustomDB
generator_class: my_package.generators.CustomGenerator
# Arbitrary engine connection parameters forwarded to db_config.yaml:
database: default
server: /custom/endpoint
max_executions_per_minute: 100
---
kind: tool
name: my_custom_db-list-schemas
type: my_custom-list-schemas
source: my_custom_db
description: List tables and schemas for the target custom database.
---
kind: tool
name: my_custom_db-execute-sql
type: my_custom-execute-sql
source: my_custom_db
description: Execute SQL queries against the target custom database.
```

## Integration Options

AutoCtx provides two ways to connect custom engines:

### 1. In `tools.yaml` (Standard)
For most custom engines, internal connections, or existing client libraries:
1. Set `type: custom` (or specify `connector_class` / `generator_class`) in the `tools.yaml` source block.
2. All custom connection parameters defined in the source block (e.g., `server`, `database_name`, `max_executions_per_minute`) are forwarded directly into `db_config.yaml` and `model_config.yaml`.
3. If `generator_class` is omitted, the framework defaults to the standard QueryData API model configuration.

### 2. External Plugin Package (Advanced)
For packaging reusable database engines as standalone Python libraries (e.g. Snowflake, Databricks, ClickHouse) without modifying core AutoCtx code:
1. Implement a custom subclass of `BaseDBConfigGenerator` defining custom validation and YAML emission.
2. In your module, export a `CUSTOM_GENERATORS` dictionary mapping source type keys to generator classes:
   ```python
   CUSTOM_GENERATORS = {
       "snowflake": SnowflakeConfigGenerator,
   }
   ```
3. Set the environment variable `AUTOCTX_CUSTOM_GENERATORS=my_package.generators`. AutoCtx will dynamically import and register these engines into the factory.

---

## Duck-Typed Interfaces

Custom classes loaded dynamically by EvalBench do **not** need to inherit from EvalBench base classes. They only need to satisfy the minimal duck-typed interfaces:

### Database Connector Interface
Custom connector classes instantiated via `connector_class`:
- **`__init__(self, db_config: dict[str, Any])`**: Receives the contents of `db_config.yaml`.
- **`execute(self, query: str, eval_query: str = None, **kwargs)`**: Required. Executes the SQL query and returns a 3-tuple `(result, eval_result, error)`. `result` must be a `list[dict[str, Any]]` mapping column names to values, or `None`/`[]` for 0 rows. Non-dict rows (e.g. unmapped tuples) will raise `TypeError` immediately at the evaluation boundary. If using a DB cursor that yields tuples, convert each row with `[dict(zip(column_names, row)) for row in rows]`. `error` must be `None` on success or an error message / `Exception` on failure.
- **`clean_tmp_creations(self)`**: Optional. Cleans up any temporary tables or artifacts created during execution. Checked via `hasattr` before invocation.
- **`close_connections(self)`**: Optional. Closes any open connection pools. Checked via `hasattr` before invocation.

### Model Generator Interface
Custom generator classes instantiated via `generator_class`:
- **`__init__(self, config: dict[str, Any])`**: Receives the contents of `model_config.yaml`.
- **`generate(self, prompt: str, **kwargs) -> str`**: Required. Generates the SQL query response for the given prompt.
