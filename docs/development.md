# Local development

This project ships as both a Gemini CLI extension and a Claude Code
plugin from a shared `plugin/` payload. Each client has its own
local-dev flow.

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
claude --plugin-dir /absolute/path/to/db-context-enrichment/dev-plugin
```

Add a shell alias if you do this often. Skill edits pick up via
`/reload-plugins`; `src/` edits require `/quit` + relaunch.

### Revert

Stop passing `--plugin-dir` and run `claude` normally. No uninstall
step — `--plugin-dir` only affects the session it's passed to.

### Notes

- `dev-plugin/.claude-plugin/plugin.json` is a separate manifest from
  `plugin/.claude-plugin/plugin.json`. It runs the server via `uv run
  --directory ${CLAUDE_PLUGIN_ROOT}/..` instead of `uvx pkg@<version>`,
  so no PyPI fetch and no version sync with `pyproject.toml` is
  required. It uses `name: db-context-engineering-dev` so its skills
  appear under `/db-context-engineering-dev:<skill>` and don't
  collide with a prod install.
- `dev-plugin/skills` is a symlink to `plugin/skills/`, so the two
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
