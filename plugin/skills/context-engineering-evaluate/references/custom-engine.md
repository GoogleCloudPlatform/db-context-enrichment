# Pluggable / Custom Database Engine Evaluation Reference

When evaluating a custom or pluggable database engine via EvalBench, the generated configurations decouple evaluation execution from proprietary database engines or model runners.

## Configuration Structure

EvalBench generates the following configuration layout for custom engines:

### 1. `db_config.yaml`
```yaml
db_type: custom
connector_class: my_package.connectors.CustomDB
dialect: googlesql
max_executions_per_minute: 100
```
EvalBench dynamically imports `connector_class` using standard Python module import syntax (`module.submodule.ClassName` or `module:ClassName`).

### 2. `model_config.yaml`
```yaml
generator: custom
generator_class: my_package.generators.CustomGenerator
context_set_id: projects/my-project/locations/us-central1/contextSets/my-context-set@v1
```
EvalBench dynamically imports `generator_class` to execute generation requests.

### 3. `run_config.yaml`
```yaml
dataset_config: autoctx/experiments/<experiment_name>/eval_configs/golden_queries.json
dataset_format: evalbench-standard-format
database_configs:
 - autoctx/experiments/<experiment_name>/eval_configs/db_config.yaml
dialect: googlesql
model_config: autoctx/experiments/<experiment_name>/eval_configs/model_config.yaml
...
```

---

## Duck-Typed Interfaces

Custom classes loaded dynamically by EvalBench do **not** need to inherit from EvalBench base classes:

- **Connector Contract**: `execute(self, query: str, eval_query: str = None, **kwargs) -> tuple[list[Any] | None, list[Any] | None, str | Exception | None]`. Optional methods: `clean_tmp_creations()`, `close_connections()`.
- **Generator Contract**: `generate(self, prompt: str, **kwargs) -> str`.

## Integration Options

1. **In `tools.yaml` (Standard)**: Configure `type: custom` (or define `connector_class` / `generator_class`) in `tools.yaml`. All custom parameters are forwarded directly into `db_config.yaml` and `model_config.yaml`.
2. **External Plugin Package (Advanced)**: External packages can register full custom engine generators via `AUTOCTX_CUSTOM_GENERATORS=my_pkg.generators` (exporting a `CUSTOM_GENERATORS` dict).
