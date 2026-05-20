# wiki-viewer

A Claude Code skill that serves a generated GCP customer-context wiki
as a browseable local HTML site. Sidebar tree navigation, GitHub-style
markdown rendering, breadcrumb headers, and intra-wiki link rewriting.

The parameterized form of the repo's [`try.sh`](../../try.sh) demo —
`try.sh` only serves the bundled sample wiki; this skill works on any
wiki dir.

## When to use

- After the [customer-context-builder skill](../customer-context-builder/)
  finishes building a wiki, when you want to inspect the output
- To explore an old wiki that's already on disk
- To browse the bundled sample wiki without touching `try.sh`

## Install

```bash
# From the repo root:
ln -s "$PWD/skills/wiki-viewer" ~/.claude/skills/wiki-viewer
# OR run the bundled installer:
bash install.sh wiki-viewer
```

No Python deps beyond stdlib (`http.server`, `pathlib`, etc.). Python
3.9+.

## Use

In Claude Code:

> Show me the wiki at `./customer-context/wikis/nordstrom/`

> Open the customer-context wiki in a browser

> Serve the LLM wiki on port 9000

Or directly via the wrapper (auto-detects the wiki at standard paths):

```bash
bash skills/wiki-viewer/scripts/serve_wiki.sh

# or with explicit args:
bash skills/wiki-viewer/scripts/serve_wiki.sh \
  --wiki-dir=./customer-context/wikis/nordstrom \
  --port=8765

# legacy single-wiki layout (no wikis/ parent) — render all 5 tabs anyway:
bash skills/wiki-viewer/scripts/serve_wiki.sh \
  --wiki-dir=./wiki/context/nordstrom \
  --bootstrap-tabs --customer-name=nordstrom --wiki-name=nordstrom-kc
```

### `--bootstrap-tabs`

The viewer renders the 4 Tickets/Candidates/Skills/Drift tabs only when
the `--wiki-dir` is part of a context-center layout — i.e., when it's at
`<root>/wikis/<customer>/<wiki-name>/`. If your wiki lives in a single
dir like `wiki/context/<customer>/`, the auto-detection falls back to
single-wiki mode and you only get the Wikis tab.

`--bootstrap-tabs` synthesizes the context-center layout in a sibling
`.cc-bootstrap/` dir at run time:

- The wiki is copied to `<.cc-bootstrap>/wikis/<customer>/<wiki-name>/`
  (override the slugs with `--customer-name` and `--wiki-name`; both
  default to the wiki dir basename).
- Empty placeholder dirs are created for `tickets/`, `candidates/`,
  `skills/`, `drift/` — they render as "No items yet".
- The bootstrap dir is wiped and regenerated each run; your original
  `--wiki-dir` is never modified.

The four placeholder tabs only become *useful* once you wire up the live
server's action endpoints (Rescan / Generate culprit-finding skill /
Create skill / Re-scan drift), which need the `claude` CLI and a
`--proposals-repo`. Bootstrapping just makes the tabs visible.

## Layout

```
skills/wiki-viewer/
├── SKILL.md
├── README.md
└── scripts/
    ├── serve_wiki.sh         # build + serve in one step
    ├── build_html_site.py    # markdown → HTML site generator for all 5 tabs (Wikis / Tickets / Candidates / Skills / Drift)
    ├── scan_candidates.py    # cluster-mode + --ticket-file mode candidate generator (invoked from /api/rescan and /api/scan-from-ticket)
    ├── score_candidates.py   # bridge_score per candidate (severity × coverage over GAPS.json)
    └── promote_server.py     # static server + POST /api/{promote,rescan,scan-from-ticket,create-skill,promote-skill,acknowledge-drift,rescan-drift}
```

## How auto-detection works

If `--wiki-dir` is omitted, `serve_wiki.sh` looks for these paths in
order and uses the first one that exists and contains at least one
`.md` file:

1. First customer subdir under `./customer-context/wikis/` — the
   standard live output of the wiki-builder skill (Context Center
   layout; all 5 tabs render automatically via `--data-dir`
   auto-detect)
2. `./customer-context/context/` — legacy single-wiki layout (only
   the Wikis tab unless you pass `--bootstrap-tabs`)
3. `./examples/sample_output/` — the bundled sample wiki for demos

If none are found, it prints a remediation message and exits.

## Stop the server

```bash
# In the running shell: Ctrl-C
# In another shell:
lsof -ti :8765 | xargs kill
```
