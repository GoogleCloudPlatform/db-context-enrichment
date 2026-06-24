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

### Pull request titles

PR titles must follow the [Conventional Commits](https://www.conventionalcommits.org/)
format. PRs are squash-merged onto `main`, and the title becomes the squashed
commit message — which Release-Please then parses to generate
[CHANGELOG.md](CHANGELOG.md) and pick the next version. A malformed title means
a missing or miscategorized changelog entry.

**Format:** `<type>[optional scope]: <description>`

Examples:
- `feat(autoctx): add hill-climbing convergence check`
- `fix(evaluate): handle missing scores.csv`
- `feat!: drop legacy /autoctx:* slash commands`
- `docs(skills): clarify bootstrap upload-URL step`

#### Types

| Type | Description | Version bump |
| :--- | :--- | :--- |
| **BREAKING CHANGE** | Anything with `!` after the type/scope (e.g. `feat!:` or `fix(api)!:`) introduces a breaking API change. | major |
| **feat** | New user-visible feature. | minor |
| **fix** | Bug fix. | patch |
| **perf** | Performance improvement with no behavior change. | patch |
| **docs** | Documentation only. | none |
| **refactor** | Code change that is neither a feat nor a fix and does not change behavior. | none |
| **test** | Adding or fixing tests. | none |
| **build** | Build system, packaging, or dependency changes (used by Dependabot). | none |
| **ci** | CI configuration files or scripts. | none |
| **chore** | Anything else (internal cleanup, release commits). | none |
| **revert** | Reverting a previous commit. | none |
| **style** | Formatting and whitespace only (rare with auto-formatters). | none |

By default, only `feat`, `fix`, `perf`, and `revert` appear in the user-facing
changelog; other types are accepted but hidden. Breaking changes always appear
in their own top section regardless of the underlying type — even `chore!:` or
`refactor!:` will be announced. Use `chore` or `refactor` (without `!`) for
internal-only PRs you do not want surfaced in release notes.

Titles are enforced by
[.github/workflows/lint-pr-title.yml](.github/workflows/lint-pr-title.yml).
PRs with malformed titles fail the check and cannot merge.

## Further reading

- [docs/development.md](docs/development.md) — local dev setup and
  edit-test loops for the Gemini CLI extension and the Claude Code
  plugin.
- [docs/releasing.md](docs/releasing.md) — release pipeline, version
  pinning, and the (skills + server) atomicity invariant.
