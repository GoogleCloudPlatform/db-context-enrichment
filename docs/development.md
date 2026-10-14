# Local development

This project ships as a Gemini CLI extension, a Claude Code plugin,
and an Antigravity CLI extension, all from a shared `plugin/` payload
(`plugin/skills/`). Each client has its own local-dev flow.

## MCP servers

Every manifest declares three MCP servers:

| Key | What | Transport |
| :--- | :--- | :--- |
| `db-context-engineering` (`mcp_db_context_engineering` in `plugin/gemini-extension.json`) | This repo's Python server (`main.py`): dataset generation/splitting, Evalbench config generation, `mutate_context_set`, `validate_context_set`, `read_evaluation_result`. | stdio (`uvx` / `uv run`) |
| `toolbox` | MCP Toolbox for Databases. Reads the single shared `.context-engineering/tools.yaml` (one file for all experiments; it may hold several sources — each experiment records the source/tools it uses in its `experiment_state.md`). Next to it, `.context-engineering/workspace_state.md` holds the workspace inputs the user entered once (Context Set project/location, Default DB source, enrichment sources, upload preference); experiments under `.context-engineering/experiments/<name>/hillclimb/experiment_state.md` record only their own run — see `plugin/skills/context-engineering-hillclimb/references/layout.md`. The client starts Toolbox with a fixed `--config`, so **any edit to `tools.yaml` requires restarting the `toolbox` MCP server** (or the client) before the new sources/tools are visible. | stdio (`uvx`) |
| `contextmgmt` | The **remote OneMCP Context Set server** (Dataplex): `list_context_set_locations`, `upload_context_set`, `get_context_set`, `delete_context_set`, `get_operation`. | Streamable HTTP, Google-credentials auth |

### Context Set server (`contextmgmt`)

The Context Set tools are **not** implemented in this repo; the agent
calls the remote server directly. All manifests point at **prod**
(`https://dataplex.googleapis.com/mcp/managed-context-sets`). The skills are
written against the server's advertised tool schema: camelCase arguments
(`projectId` / `location` / `contextSetId` / `contextPayload` /
`operationId`) and the structured `databases` field
(`{databaseType, projectId, location, clusterId, instanceId, databaseId}`,
cl/995847938). If a change lands on staging first, switch every manifest
(`plugin/mcp_config.json`, `plugin/gemini-extension.json`,
`plugin/.claude-plugin/plugin.json`, `plugin/mcp.json`, root
`gemini-extension.json`, `dev-plugin/*`) to
`https://staging-dataplex.sandbox.googleapis.com/mcp/managed-context-sets`
for the test and flip them back afterwards.

Auth is `authProviderType: "google_credentials"`: the client mints a
bearer token from Application Default Credentials (scope
`cloud-platform`) and sets `X-Goog-User-Project` from the ADC quota
project. Before launching an agent:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <project>
```

Client support:

- **Antigravity / Jetski** — `plugin/mcp_config.json` (`url` +
  `authProviderType`). Supported natively.
- **Gemini CLI** — `gemini-extension.json` / `plugin/gemini-extension.json`
  (`httpUrl` + `authProviderType` + `oauth.scopes`). Supported natively.
- **Claude Code** — `plugin/.claude-plugin/plugin.json` (`type: http` +
  `url` + `headersHelper`). Claude has no native Google-credentials
  provider, so `plugin/scripts/adc_headers.sh` mints the headers from ADC
  (`Authorization: Bearer <token>` and `X-Goog-User-Project` from the ADC
  quota project). Claude re-runs the helper on 401/403, which covers token
  expiry. Only dependency: `gcloud` on `PATH`. **Untested by the
  core team so far** — verified by contributors with Claude Code access.
- **Agent Plugins clients** (`plugin/mcp.json`, VS Code / Cursor / …) —
  declared as `type: streamable-http` + `url`. That spec has no auth-provider
  or dynamic-header hook, so authentication is the **host client's**
  responsibility (a client that can attach Google credentials to HTTP MCP
  servers works out of the box; others need a static `headers` entry with a
  bearer token and `X-Goog-User-Project`, which we do not ship).

### Antigravity tool-name length limit

Antigravity (desktop and `agy`) exposes plugin MCP tools to the model as
`mcp_<plugin-name>_<server-key>_<tool>` and rejects any name longer than
**64 characters** (the tool is logged as `encountered invalid tool` and
is not callable). The budget is therefore
`64 − 4 − len(plugin) − len(server-key) − 2` characters for the tool
name; the longest tools are `list_context_set_locations` and
`generate_evalbench_configs` (26 each).

- `dev-plugin/gemini-extension.json` uses the short plugin name
  `dbce-dev` so every tool fits during local testing
  (`mcp_dbce-dev_contextmgmt_list_context_set_locations` = 51,
  `mcp_dbce-dev_db-context-engineering_generate_evalbench_configs` = 62).
- The shipped Antigravity manifest (root `gemini-extension.json`, name
  `google-cloud-db-context-engineering`) currently **overflows for most
  tools** of all three servers. Shortening the shipped plugin name
  and/or the `db-context-engineering` server key is tracked as a
  follow-up; keep every new server key short.

## Gemini CLI extension

### Set up

```bash
gemini extensions link /absolute/path/to/db-context-enrichment/plugin
```

Verify:

```bash
gemini extensions list   # Type: link, Path: .../plugin
gemini mcp list          # mcp_db_context_engineering ✓ Connected, contextmgmt ✓ Connected
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

Edit `dev-plugin/mcp_config.json`:

1. Replace `<local-repo-path>` in `mcpServers.db-context-engineering.args`
   with the absolute path to this repo's root.
2. Replace `<local-workspace-path>` in the `cwd` of **both** stdio servers
   (`db-context-engineering` and `toolbox`) with the absolute path of the
   directory you will launch `agy` in — the one that holds
   `.context-engineering/tools.yaml`.

> **Why `cwd` is required on Antigravity.** For plugin MCP servers,
> Antigravity/Jetski resolves an empty `cwd` to the *plugin directory*
> (`~/.gemini/config/plugins/<name>/`), not to the workspace. Toolbox then
> looks for `.context-engineering/tools.yaml` inside the plugin directory
> and fails with `no such file or directory`, and relative paths passed to
> the local server's tools resolve there too. There is no
> workspace-root variable for plugin manifests today (only `${PLUGIN_ROOT}`
> and `${PLUGIN_DATA}`), so the dev manifest pins an absolute `cwd`. Gemini
> CLI and Claude Code start plugin servers in the workspace, so their
> manifests do not need this. The shipped Antigravity manifest has the
> same gap — tracked as a follow-up.

Make sure ADC is in place (see
[Context Set server](#context-set-server-contextmgmt)), then install the dev plugin:

```bash
agy plugin install /absolute/path/to/db-context-enrichment/dev-plugin
```

Verify:

```bash
agy plugin list                                   # dbce-dev
cat ~/.gemini/config/plugins/dbce-dev/mcp_config.json   # must still contain "authProviderType"
```

Then launch `agy` in a workspace directory and open `/mcp`: the plugin
should show three servers (`db-context-engineering`, `toolbox`,
`contextmgmt`) and the model-facing tool names
`mcp_dbce-dev_<server>_<tool>` must all be connected (none flagged
invalid). A quick end-to-end check is asking the agent to call
`list_context_set_locations` for a project you can access.

`src/` and `plugin/skills/` edits are picked up on the next `agy`
launch. **Manifest edits are not**: `agy plugin install` copies the
directory, so re-run the install command after changing
`dev-plugin/plugin.json` or `dev-plugin/mcp_config.json`.

### Revert

```bash
agy plugin uninstall dbce-dev
```

### Notes

- `dev-plugin/plugin.json` + `dev-plugin/mcp_config.json` are the
  native Antigravity manifest pair and are what `agy plugin install`
  reads when `plugin.json` is present. Do **not** rely on
  `dev-plugin/gemini-extension.json` for agy: when a directory has only
  a `gemini-extension.json`, agy runs its Gemini-extension importer,
  which keeps `url` but **drops `authProviderType`**, so the remote
  Context Set server would come up unauthenticated. The
  `gemini-extension.json` is kept in sync for reference only.
- The dev plugin is named `dbce-dev` (not
  `google-cloud-db-context-engineering-dev`) because Antigravity rejects
  model-facing tool names longer than 64 characters — see
  [Antigravity tool-name length limit](#antigravity-tool-name-length-limit).
  With the long name every tool of every server was invalid.
- The dev manifest runs the server via `uv run --project
  <local-repo-path>` instead of `uvx pkg@<version>`, so no PyPI fetch
  and no version sync with `pyproject.toml` is required. It takes a
  literal `<local-repo-path>` placeholder rather than
  `${extensionPath}/..` so the working directory resolves unambiguously
  regardless of how Antigravity launches the subprocess. Keep the
  placeholder in the committed file; only your working copy carries
  the absolute path.
- `dev-plugin/skills` is a symlink to `plugin/skills/`, and the root
  `skills` symlink also targets `plugin/skills/`, so all three variants
  (Gemini CLI, Claude Code, Antigravity) share skill files. The
  manifests themselves are hand-maintained — when changing the prod
  root manifest, mirror any structural change (e.g. adding an MCP
  server entry) into `dev-plugin/mcp_config.json`.
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


