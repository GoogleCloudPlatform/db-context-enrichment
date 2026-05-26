# How to contribute

We'd love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our community guidelines

This project follows
[Google's Open Source Community Guidelines](https://opensource.google/conduct/).

## Contribution process

### Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more
information on using pull requests.

## Local Gemini CLI extension development

The published extension is installed via `gemini extensions install
<github-url>`, which downloads a pre-built release archive containing
PyInstaller-bundled binaries. For local development, use
`gemini extensions link` to point Gemini at your working tree
directly — no fork, release, or editable `uv tool install` needed.

From the repo root, in a fresh shell:

```bash
gemini extensions link /absolute/path/to/db-context-enrichment/plugin
```

Verify it loaded and the MCP server connects:

```bash
gemini extensions list   # should show Type: link, Path: .../plugin
gemini mcp list          # mcp_db_context_engineering should show ✓ Connected
```

Edit-test loop:

- **Python source (`src/`)**: edit and save. The next `gemini` invocation
  launches a fresh MCP subprocess via `uv run --directory
  ${extensionPath}/..`, which resolves to the repo root (where
  `pyproject.toml` lives) and picks up your changes. No reinstall, no
  editable tool install — `uv run` reads source from the project tree
  directly.
- **Skills / commands / `GEMINI.md` (`plugin/`)**: edit and save. Because
  `link` registers the path rather than copying files, edits are picked
  up on the next `gemini` launch with no relink needed.

To return to the released version:

```bash
gemini extensions uninstall google-cloud-db-context-engineering
gemini extensions install https://github.com/GoogleCloudPlatform/db-context-enrichment
```

Both the linked dev extension and the released extension are named
`google-cloud-db-context-engineering`, so only one can be installed at a
time. Always `gemini extensions uninstall google-cloud-db-context-engineering`
before installing the other variant.

For integration-testing the full PyInstaller-bundled release (Evalbench
+ Toolbox binaries), see the "Development and Testing" section in
`README.md` for the fork-and-release workflow.

## Local Claude Code plugin development

The published plugin runs the MCP server via `uvx
google-cloud-db-context-engineering`, which fetches the released wheel
from PyPI. Local development needs two pieces:

- **MCP server source**: register the working tree as an editable `uv`
  tool so `uvx` resolves to your source instead of PyPI.
- **Plugin payload (skills/commands/agents)**: install from a local-path
  marketplace (`dev/.claude-plugin/marketplace.json`) instead of the
  prod marketplace, whose `source` is `git-subdir` pinned to the latest
  released tag and so does not see your working tree.

One-time setup (from the repo root):

```bash
uv tool install --editable .
```

Then in Claude Code (from any directory):

```
/plugin marketplace add /absolute/path/to/db-context-enrichment/dev
/plugin install db-context-engineering@db-context-enrichment-marketplace-dev
/reload-plugins
```

Edit-test loop:

- **Python source (`src/`)**: edit and save. The editable install means
  `uvx` already resolves to your working tree, but **`/reload-plugins`
  will not restart an already-running MCP subprocess** (it does start
  one on first install, and it does reload skills/commands/agents/hooks
  — it just won't respawn the running MCP server, despite reporting "N
  plugin MCP servers" in its output). You need to `/quit` Claude Code
  and relaunch it for src/ edits to take effect.
- **Skills / commands (`plugin/skills/`, `plugin/commands/`)**: edit and
  run `/plugin update` to refresh the install cache. Claude Code copies
  plugin files to a cache at install time, so source-tree edits don't
  propagate until a refresh. Fall back to `/plugin uninstall` +
  `/plugin install` if update misses the change.

To return to the released version: `uv tool uninstall
google-cloud-db-context-engineering` and reinstall from the prod
marketplace.

The dev marketplace and prod marketplace both register a plugin named
`db-context-engineering`. Install only one at a time. Why the two
marketplaces exist:

- `.claude-plugin/marketplace.json` (prod): `source` is `git-subdir`
  pinned to the released tag — minimal payload pulled from GitHub for
  end users.
- `dev/.claude-plugin/marketplace.json` (dev): `source` is `./plugin`
  pointing at a symlink (`dev/plugin -> ../plugin`) back to the shared
  payload, so dev installs read your working tree directly. (The
  validator rejects `..` in source paths, hence the symlink.)

Note: `mcpServers` config must live in
`plugin/.claude-plugin/plugin.json`. `mcpServers` declared in
`marketplace.json` is silently ignored at startup regardless of the
`strict` setting. Display metadata (description, license, homepage,
keywords) can live in either file — the marketplace entry's values are
used at install time for catalog listing.
