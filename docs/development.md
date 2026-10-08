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
- The MCP subprocess launches via `uv run --directory
  ${extensionPath}/..`, which resolves to the repo root.

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

 
## Running Tests

### Unit Test and Linting

```bash
# Run code formatting and linter
uv run ruff check --fix .

# Run pytest unit test suite
uv run --extra test pytest tests/
```
 
### Integration Testing (Fork & Release Workflow)

To test a new feature with the full PyInstaller-bundled binaries (including Evalbench + Toolbox executables):

1. **Create a fork** of the repository on GitHub.
2. **Set up the fork/upstream remotes** in your local environment:
   ```bash
   git clone https://github.com/YOUR-USERNAME/db-context-enrichment.git
   git remote add upstream https://github.com/GoogleCloudPlatform/db-context-enrichment
   ```
3. **Develop changes** in a new branch and push them to your fork.
4. **Create a new release tag** on your fork (e.g. `0.0.1-test`).
5. Wait for the release assets build pipeline to complete in your fork.
6. **Install the custom release** via Gemini CLI:
   ```bash
   gemini extensions install https://github.com/YOUR-USERNAME/db-context-enrichment --ref 0.0.1-test
   ```
   *Note: Use `gemini extensions uninstall google-cloud-db-context-engineering` before installing your test release.*

## Adding Custom Database Engines

AutoCtx and EvalBench support pluggable database engines and model generators via a generic Service Provider Interface (SPI). There are two ways to integrate a custom database engine without modifying core framework code:

### Option 1: Config-Driven SPI in `tools.yaml`

Specify `type: custom` (or attach `connector_class` / `generator_class`) directly in a `tools.yaml` source block:

```yaml
kind: source
name: my_custom_db
type: custom
dialect: googlesql
connector_class: my_package.connectors.CustomDB
generator_class: my_package.generators.CustomGenerator
database: default
server: /custom/endpoint
max_executions_per_minute: 100
```

- All non-meta fields in the source block are forwarded into `db_config.yaml` and `model_config.yaml`.
- If `generator_class` is omitted, `model_config.yaml` falls back to the standard `query_data_api` generator.
- Custom classes are dynamically imported by EvalBench and only need to implement duck-typed interfaces:
  - **Database Connector (`connector_class`)**:
    - `__init__(self, db_config: dict[str, Any])`
    - `execute(self, query: str, eval_query: str = None, **kwargs) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None, str | Exception | None]`
    - Optional: `clean_tmp_creations(self)`, `close_connections(self)`
  - **Model Generator (`generator_class`)**:
    - `__init__(self, config: dict[str, Any])`
    - `generate(self, prompt: str, **kwargs) -> str`

### Option 2: External Plugin Package (`AUTOCTX_CUSTOM_GENERATORS`)

To register a reusable first-class `source` type with custom validation and YAML generation:

1. Subclass `BaseDBConfigGenerator` (`google.cloud.db_context_enrichment.evaluate.db_generators.base.BaseDBConfigGenerator`) and implement `generate_db_config()` and `build_datasource_reference()`.
2. Export a `CUSTOM_GENERATORS: dict[str, type[BaseDBConfigGenerator]]` dictionary from your Python module mapping the `tools.yaml` `type` string to your generator class:
   ```python
   CUSTOM_GENERATORS = {
       "snowflake": SnowflakeConfigGenerator,
   }
   ```
3. Set `AUTOCTX_CUSTOM_GENERATORS=<your_python_module_path>` in the environment before running `generate_evalbench_configs`.

See the skill references in [plugin/skills/context-engineering-init/references/custom-engine.md](../plugin/skills/context-engineering-init/references/custom-engine.md) and [plugin/skills/context-engineering-evaluate/references/custom-engine.md](../plugin/skills/context-engineering-evaluate/references/custom-engine.md) for full details.


