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

The published plugin (`.claude-plugin/marketplace.json`) runs the MCP server
via `uvx`, which pulls the released wheel from PyPI. For iterating on the
Python source in `src/` without a release, install a dev variant of the
plugin that runs the MCP server from your working tree via `uv run`.

One-time setup:

```bash
cp .claude-plugin/marketplace-dev.json.example .claude-plugin/marketplace-dev.json
# Edit the file: replace <REPLACE_WITH_ABS_REPO_PATH> with $(pwd)
```

Then in Claude Code:

```
/plugin marketplace add .
/plugin install db-context-engineering@db-context-enrichment-marketplace-dev
```

The dev marketplace and prod marketplace both register a plugin named
`db-context-engineering`. Enable only one at a time — disable the prod
plugin before enabling the dev plugin (or simply do not add the prod
marketplace in your dev environment).

Edit-test loop:

- **Python source (`src/`)**: edit and save. `uv run --project` picks up
  changes on the next MCP tool invocation. No reinstall needed.
- **Skills / commands (`plugin/skills/`, `plugin/commands/`)**: edit and
  run `/plugin update` (or uninstall + install). Claude Code copies plugin
  files to a cache on install, so reinstall is required.

`marketplace-dev.json` is gitignored. Each collaborator maintains their own
copy with their own absolute path.
