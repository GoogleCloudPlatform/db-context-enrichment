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

Then in Claude Code:

```
/plugin marketplace add /absolute/path/to/db-context-enrichment/dev
/plugin install db-context-engineering@db-context-enrichment-marketplace-dev
/reload-plugins
```

Edit-test loop:

- **Python source (`src/`)**: edit and save. The editable install means
  `uvx` already resolves to your working tree, so changes take effect on
  the next MCP server restart. `/reload-plugins` restarts the server.
- **Skills / commands (`plugin/skills/`, `plugin/commands/`)**: edit and
  run `/plugin update` (or uninstall + install). Claude Code copies
  plugin files to a cache on install, so a reinstall is required to
  pick up changes.

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

Note: `mcpServers` config is read from
`plugin/.claude-plugin/plugin.json`, not from `marketplace.json`. The
marketplace entry's other fields (description, license, homepage,
keywords) are authoritative because `strict: false` is set.
