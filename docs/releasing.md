# Release process

## Release atomicity (Claude Code)

End users must never see a mismatched (skills + server) pair, so the
release pipeline coordinates two pins:

```mermaid
sequenceDiagram
    autonumber
    actor M as Maintainer
    participant RP as release-please PR
    participant CI as release.yml
    participant PyPI
    participant Pin as pin-marketplace-ref
    participant MP as marketplace.json
    actor U as End user

    M->>RP: merge
    Note right of RP: release-please bumps version<br>sync-mcp-version rewrites uvx pin to match
    RP->>CI: tag pushed
    CI->>PyPI: publish wheel
    Note right of PyPI: T1 — new server live on PyPI<br>marketplace ref still points to old tag<br>users stay on old skills and old server
    Pin->>PyPI: poll until version indexed
    Pin->>M: open ref-bump PR
    M->>MP: merge ref-bump PR
    Note right of MP: T2 — marketplace ref points to new tag<br>new plugin.json bundles new uvx pin
    U->>U: run plugin update and restart Claude
    Note right of U: atomic transition<br>new skills and new uvx pin arrive together
```


1. **`plugin/.claude-plugin/plugin.json` keeps `$.version` and the
   `mcpServers.db-context-engineering.args[0]` uvx pin
   (`google-cloud-db-context-engineering@<version>`) in sync.**
   - `release-please` bumps `$.version` directly via its `json` updater.
   - `.github/workflows/sync-mcp-version.yml` runs on each
     release-please PR and amends a follow-up commit that rewrites
     `args[0]` to match.
   - The `validate-mcp-version-pin` presubmit job fails any PR where
     the two fields diverge — a guard in case the sync workflow
     silently breaks.
2. **`.claude-plugin/marketplace.json` `source.ref` points at the
   latest released tag.**
   - The `pin-marketplace-ref` job in `release.yml` waits for the PyPI
     wheel to be indexed before opening the bump PR, so the
     marketplace never points at a version `uvx` cannot install.

The transition point is the merge of `pin-marketplace-ref`'s PR: before
the merge users stay on the old `(skills, server)` pair, after the
merge `/plugin update` + Claude restart flips both pins to the new
version together. The restart is required because Claude Code's
`/reload-plugins` does not respawn the MCP subprocess — same limitation
flagged in the Claude Code plugin notes in
[development.md](development.md#notes-1).

## Release atomicity (Gemini CLI)

Atomicity is automatic — skills and the MCP server binary ship in the
same release tarball, so there is nothing to coordinate across pins.

1. **`plugin/gemini-extension.json` `$.version` is bumped by
   release-please alongside `plugin.json`.**
   - On the release tag, `release.yml` → `build-artifacts` builds a
     PyInstaller binary per platform.
   - The job rewrites
     `mcpServers.mcp_db_context_engineering.command` to point at the
     bundled `${extensionPath}/google-cloud-db-context-engineering`
     binary, then archives skills + manifest + binary into a single
     `<platform>.<arch>.google-cloud-db-context-engineering.tar.gz`.
   - The archives are uploaded as GitHub Release assets.
2. **End users install/update via `gemini extensions install
   <github-url>` (or `gemini extensions update`), which fetches the
   latest release tarball.**
   - Because skills and binary live in the same archive, version skew
     between the two is impossible — there is no separate package
     index (PyPI) and no separate marketplace pin to coordinate.

The contrast with Claude Code: Claude Code splits the payload across a
PyPI wheel (server) and a marketplace ref (skills), so atomicity has to
be reconstructed by the `pin-marketplace-ref` gate. Gemini CLI bundles
both into one archive, so the GitHub release tag itself is the atomic
unit.
