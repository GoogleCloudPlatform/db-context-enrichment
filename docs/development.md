# Local development

This project ships as a Gemini CLI extension, a Claude Code plugin,
and an Antigravity CLI extension, all from a shared `plugin/` payload
(skills/commands/`GEMINI.md`). Each client has its own local-dev flow.

## Gemini CLI extension

### Set up

```bash
gemini extensions link /absolute/path/to/db-context-enrichment/plugin
```

Verify:

```bash
gemini extensions list   # Type: link, Path: .../plugin
gemini mcp list          # mcp_db_context_engineering ✓ Connected
```

Both `src/` and `plugin/` edits are picked up on the next `gemini`
launch — no relink or reinstall.

### Revert

```bash
gemini extensions uninstall google-cloud-db-context-engineering
gemini extensions install https://github.com/GoogleCloudPlatform/db-context-enrichment
```

### Notes

- The linked dev extension and the released extension share the name
  `google-cloud-db-context-engineering`, so only one can be installed
  at a time. Always uninstall before switching.
- The MCP subprocess launches via `uv run --directory
  ${extensionPath}/..`, which resolves to the repo root.
- For integration-testing the full PyInstaller-bundled release
  (Evalbench + Toolbox binaries), see the "Development and Testing"
  section in [README.md](../README.md).

## Claude Code plugin

### Set up

```bash
claude --plugin-dir /absolute/path/to/db-context-enrichment/dev-plugin/plugin
```

Add a shell alias if you do this often. Skill edits pick up via
`/reload-plugins`; `src/` edits require `/quit` + relaunch.

### Revert

Stop passing `--plugin-dir` and run `claude` normally. No uninstall
step — `--plugin-dir` only affects the session it's passed to.

### Notes

- `dev-plugin/plugin/.claude-plugin/plugin.json` is a separate manifest from
  `plugin/.claude-plugin/plugin.json`. It runs the server via `uv run
  --directory ${CLAUDE_PLUGIN_ROOT}/..` instead of `uvx pkg@<version>`,
  so no PyPI fetch and no version sync with `pyproject.toml` is
  required. It uses `name: db-context-engineering-dev` so its skills
  appear under `/db-context-engineering-dev:<skill>` and don't
  collide with a prod install.
- `dev-plugin/plugin/skills` is a symlink to `plugin/skills/`, so the two
  variants share skill files. The manifests themselves are
  hand-maintained — when changing the prod manifest, mirror any
  structural change (e.g. adding an MCP server entry) into the dev
  manifest.
- `/reload-plugins` does **not** respawn an already-running MCP
  subprocess (it reloads skills/agents/hooks and starts the server on
  first load, but won't restart a running one — despite reporting "N
  plugin MCP servers" in its output). This is why `src/` edits need a
  full `/quit` + relaunch.
- `mcpServers` config must live in `.claude-plugin/plugin.json`;
  declarations in `marketplace.json` are silently ignored at startup
  regardless of the `strict` setting.
- See [releasing.md](releasing.md) for the production version-pinning
  mechanics that the dev flow sidesteps.

## Antigravity CLI extension

### Set up

Edit `dev-plugin/gemini-extension.json` and replace the `<local-repo-path>`
placeholder in `mcpServers.db-context-engineering.args` with the absolute
path to this repo's root. Then install the dev extension:

```bash
agy plugin install /absolute/path/to/db-context-enrichment/dev-plugin
```

Verify:

```bash
agy plugin list
```

Both `src/` and `plugin/` edits are picked up on the next `agy` launch.

### Revert

```bash
agy plugin uninstall google-cloud-db-context-engineering-dev
```

### Notes

- `dev-plugin/gemini-extension.json` is a separate manifest from the
  root `gemini-extension.json`. It runs the server via `uv run
  --directory <local-repo-path>` instead of `uvx pkg@<version>`, so no
  PyPI fetch and no version sync with `pyproject.toml` is required. It
  uses `name: google-cloud-db-context-engineering-dev` so it can sit
  side-by-side with a prod install without colliding.
- The dev manifest takes a literal `<local-repo-path>` placeholder
  rather than `${extensionPath}/..` so the working directory resolves
  unambiguously regardless of how Antigravity launches the subprocess
  — see the Q&A note in the commit history for the reasoning.
- `dev-plugin/skills` is a symlink to `plugin/skills/`, and the root
  `skills` symlink also targets `plugin/skills/`, so all three variants
  (Gemini CLI, Claude Code, Antigravity) share skill files. The
  manifests themselves are hand-maintained — when changing the prod
  root manifest, mirror any structural change (e.g. adding an MCP
  server entry) into the dev manifest.
- See [releasing.md](releasing.md) for the version-pin atomicity that
  the dev flow sidesteps; the agy root manifest shares the same
  `uvx pkg@<version>` invariant as the Claude Code plugin manifest.

## Adding and Evaluating Non-Public / Pre-Release Datasources

When adding support for new database engines or pre-release GDA protocol buffer fields (e.g., Spanner Graph, NoSQL engines like Firestore/Bigtable, or custom unreleased datasource references):

### 1. Implement the DB Config Generator
Create a new generator subclass inheriting from `BaseDBConfigGenerator` inside `src/google/cloud/db_context_enrichment/evaluate/db_generators/<my_db>.py`.

Implement `build_datasource_reference(self, context_set_id: str) -> dict`. Return a standard Python `dict` representing the datasource reference payload:

```python
# Example for a NoSQL or pre-release datasource reference
def build_datasource_reference(self, context_set_id: str) -> dict:
    ref = {
        "my_new_db_reference": {
            "database_reference": {
                "project_id": self.project,
                "instance_id": self.instance,
                "custom_unreleased_field": self.custom_field,
            }
        }
    }
    if context_set_id:
        ref["my_new_db_reference"]["agent_context_reference"] = {
            "context_set_id": context_set_id
        }
    return ref
```

> **Why return a `dict`?** Returning a Python `dict` instead of a compiled `gda.DatasourceReferences` protobuf object causes `BaseDBConfigGenerator` to bypass local gRPC protobuf validation, allowing unreleased/private fields to be written cleanly to `model_config.yaml`.

Register your new generator in `_get_db_generator` inside `src/google/cloud/db_context_enrichment/evaluate/evaluate_generator.py`.

### 2. Generate Evaluation Configurations
Add connection parameters to `tools.yaml` and compile experiment configs:

```bash
uv run --extra test python3 -c '
from google.cloud.db_context_enrichment.evaluate.evaluate_generator import generate_evalbench_configs
generate_evalbench_configs(
    experiment_name="my_test_exp",
    dataset_path="tests/mock_dataset.json",
    context_set_id="",  # Pass "" for context-free evaluation
    toolbox_config_path="tools.yaml",
    toolbox_source_name="my_source"
)'
```

### 3. Run Evaluation with the REST Compatibility Wrapper
Standard `google-evalbench` CLI runs rely on published PyPI client SDKs that reject unreleased protobuf fields. The compatibility wrapper (`bin/run-evalbench-compat`) implements an automatic **try-gRPC-then-fallback-to-REST** execution pattern:

```bash
uv run --with google-evalbench==1.9.0 python3 bin/run-evalbench-compat --experiment_config=autoctx/experiments/my_test_exp/eval_configs/run_config.yaml
```

> **Private Preview / Early Access Compatibility**:
> This automatic fallback enables **Private Preview customers** and **Trusted Testers** to evaluate unreleased database engines (such as Spanner Graph or NoSQL) using Crema immediately, without waiting for the public Python SDK package to be updated on PyPI.
> 
> - **How it works**: It attempts standard gRPC execution first. If the published SDK throws an exception (e.g. `ValueError: Protocol message ... has no "field"`), it catches the error and transparently delegates the JSON payload to the GDA REST API.
> - **Seamless GA Transition**: When the feature reaches General Availability (GA) and the public SDK is published to PyPI, standard gRPC calls will begin succeeding naturally without requiring any changes to customer configs or code.

#### Targeting Staging Sandbox vs Production Endpoints
- **Production (Default)**: The wrapper defaults to `geminidataanalytics.googleapis.com`.
- **Staging Sandbox**: If your new proto fields or control plane features are deployed on the GDA staging endpoint, configure `api_endpoint` in `model_config.yaml`:
  ```yaml
  # autoctx/experiments/my_test_exp/eval_configs/model_config.yaml
  generator: query_data_api
  api_endpoint: staging-geminidataanalytics.sandbox.googleapis.com
  ```

