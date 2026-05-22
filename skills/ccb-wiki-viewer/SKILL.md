---
name: skill-ccb-wiki-viewer
description: Serve a generated GCP customer-context wiki as a browseable local **Context Center** — a 5-tab HTML site (Wikis · Tickets · Candidates · Skills · Drift) over one or more customer wikis, with selection-based Edit / Promote-to-PR, ticket-driven candidate generation, headless `/skill-creator` integration, Promote-skill-to-PR, and per-entry Ack + Re-scan for drift. Use this skill whenever the user wants to "view", "browse", "open", "serve", or "preview" a wiki produced by the gcp-customer-context-builder skill — phrasings like "show me the wiki", "open the customer wiki in a browser", "let me explore the wiki", "serve the LLM wiki", "preview the context repo", "open the context center", or after building a wiki when the user wants to inspect the output, scan for reusable patterns, or check what's drifted. Works on any context-center dir; auto-detects the most likely location (first customer under ./customer-context/wikis/, then legacy ./customer-context/context/, then ./examples/sample_output/) but accepts an explicit path. No GCP credentials needed; pure-local Python 3.9+.
---

# Wiki Viewer (Context Center)

This skill builds the local **Context Center** — a 5-tab HTML viewer over
a generated customer-context wiki — and serves it on a local port so the
user can browse it in their browser. The viewer has sidebar navigation
showing the full directory tree, GitHub-style markdown rendering (via
`marked.js` from CDN), breadcrumb headers on every page, intra-wiki link
rewriting so clicking `.md` references in the rendered content navigates
correctly, and a top-level tab nav for the five sections below.

This skill is the parameterized form of the repo's `try.sh` demo
script — `try.sh` only ever serves the bundled sample wiki at
`examples/sample_output/`; this skill works on any wiki dir.

## The five tabs

The viewer is organized into five top-level sections, all rendered by
the same `build_html_site.py` (see its `SECTIONS` list):

1. **Wikis** — the per-customer wiki tree (one sub-tree per customer).
   Selecting any text in the rendered markdown pops a small toolbar with
   **Edit** and **Promote** buttons that POST to `/api/promote` and open
   PRs against `--proposals-repo`. Per-page **Gaps side panel** lists
   structural + coverage gaps from `GAPS.json`, each with a one-click
   "Promote bridge" button.
2. **Tickets** — bundled / user-loaded support tickets. Clicking a
   ticket opens it; **Generate culprit-finding skill** POSTs to
   `/api/scan-from-ticket`, which synthesizes a parameterized debugging
   workflow from the ticket text + the wiki's data model and writes it
   as a new candidate.
3. **Candidates** — auto-detected reusable workflows produced either by
   ticket-to-candidate (above) or by clustering across the wikis
   (**🔄 Rescan** button → `/api/rescan`, which shells out to
   `scan_candidates.py`). Candidates are sorted by `bridge_score` (sum
   of severity × coverage over the gaps the candidate would close —
   see `score_candidates.py`). **Create skill** POSTs to
   `/api/create-skill`, which invokes headless `/skill-creator` to
   scaffold a real skill dir from the candidate and moves it into the
   Skills tab.
4. **Skills** — promoted reusable skills (`SKILL.md` + scripts). The
   **🚀 Promote skill** button POSTs to `/api/promote-skill`, which
   ships the whole skill dir as a PR to the proposals repo.
5. **Drift** — sources that have CHANGED, gone DELETED, or appeared NEW
   since the wiki was built (per `DRIFT.md` / `DRIFT.json` produced by
   `source_diff.py`). Each entry shows severity (after two-stage
   re-validation, when present), affected narrative files, and a
   per-entry **Ack** button (`/api/acknowledge-drift`). A top-level
   **Re-scan drift** action (`/api/rescan-drift`) re-runs
   `source_diff.py` + `revalidate_drift.py` in place and refreshes the
   tab without a full rebuild.

## When to use

- After the gcp-customer-context-builder skill finishes building a wiki
  and the user wants to inspect it
- When the user asks to "browse", "view", "open", "preview", or "serve"
  a customer wiki / context repo / LLM wiki
- For a quick demo of the bundled sample wiki ("show me an example wiki")
- For exploring an old wiki that's already on disk

## Inputs

- `--wiki-dir=PATH` (optional) — the directory to serve. If omitted, the
  skill auto-detects in this order:
  1. First customer subdir under `./customer-context/wikis/` (the
     standard live output of the wiki-builder skill — Context Center
     layout; all 5 tabs render automatically)
  2. `./customer-context/context/` (legacy single-wiki layout — only
     the Wikis tab renders unless you pass `--bootstrap-tabs`)
  3. `./examples/sample_output/` if present (the bundled sample)
  4. otherwise ask the user
- `--site-dir=PATH` (optional) — where to build the HTML output.
  Default: `<wiki-dir>/../site/` (sibling of the wiki). Use the default
  unless you have a specific reason.
- `--port=N` (optional, default 8765) — local port. If taken, fail
  cleanly and ask the user for a different one.
- `--no-open` (optional) — skip auto-opening the browser. By default
  the skill opens the browser to the served root.
- `--proposals-repo=OWNER/REPO` (optional) — enables the **Promote**
  feature. When set, highlighting text in the viewer pops a "Promote"
  button; clicking it writes the selection to a new file in the named
  repo and opens a PR. Requires `gh` CLI and write access to the repo.
  When omitted, the Promote button is inert (the selection just doesn't
  POST anywhere). Default for this user: `oscarkang24/wiki-proposals`.
- `--proposals-checkout=PATH` (optional) — local cache for the
  proposals-repo clone. Default: `~/.cache/wiki-proposals`.
- `--bootstrap-tabs` (optional) — synthesize a context-center layout in a
  sibling `.cc-bootstrap/` dir so all 5 tabs render even when the wiki
  isn't already at `<root>/wikis/<customer>/<wiki-name>/`. The wiki is
  copied under `wikis/<customer>/<wiki-name>/` and empty placeholder dirs
  are created for the four other sections (they render as "No items
  yet"). Ignored if `--data-dir` was given or auto-detected. Use this
  when the wiki you're serving was built into a single-customer dir
  (e.g., `wiki/context/nordstrom/`) and you still want all 5 tabs in the
  viewer.
- `--customer-name=NAME` (optional) — overrides the customer slug used
  by `--bootstrap-tabs` (default: basename of `--wiki-dir`).
- `--wiki-name=NAME` (optional) — overrides the wiki-name slug used by
  `--bootstrap-tabs` (default: same as `--customer-name`).

## Workflow

You are the orchestrator. This skill is a single bash invocation +
brief reporting — no sub-agents needed.

### Step 1 — Resolve the wiki dir

If the user named a path, use it. Otherwise auto-detect per the order
above. If multiple candidates exist (e.g., both customer-context/ and
examples/sample_output/), prefer the user's *real* output
(`customer-context/`) over the bundled sample.

If the resolved path doesn't contain at least one `*.md` file, stop and
tell the user the directory looks empty.

### Step 2 — Verify Python is available

`python3 --version` should report 3.9+. If not, surface the install URL
and stop.

### Step 3 — Build + serve

Run [scripts/serve_wiki.sh](scripts/serve_wiki.sh) with the resolved
arguments. It:

1. Removes the previous `--site-dir` if any (clean rebuild)
2. Calls `scripts/build_html_site.py` to generate the HTML tree
3. Starts a local server on `--port`:
   - If `--proposals-repo` is set, uses
     `scripts/promote_server.py` (static files + `POST /api/promote`)
   - Otherwise uses plain `python3 -m http.server` (static-only,
     Promote button is inert)
4. Opens the browser (unless `--no-open`)

The server runs in the foreground; the user stops it with Ctrl-C. If
you're invoking this from a Claude Code session, run it as a background
task so the orchestrator can continue and report the URL.

### Step 4 — Report back

Tell the user:
- The URL they should open (e.g., `http://127.0.0.1:8765/index.html`)
- The file count and total size of the generated site
- A short list of "interesting starting points" — the customer-root
  index, the `CRITIQUE.md` if present, and the most operationally
  interesting per-table dir (look for "HIGH-severity" or "deprecated"
  in summaries)
- The Ctrl-C / `lsof -ti :8765 | xargs kill` recipe for stopping the
  server when done

## Why a separate skill rather than baking it into wiki-builder

Three reasons:

1. **Independent value** — users may want to view a wiki built in a
   prior session, or the bundled sample, without touching the
   wiki-builder skill at all.
2. **Different mental model** — the wiki-builder is a long-running
   multi-agent task; the viewer is a quick local-dev convenience.
   Keeping them separate makes each skill's purpose obvious.
3. **Safer composition** — wiki-builder can suggest invoking
   wiki-viewer at the end of a build (and its SKILL.md does), but
   doesn't auto-launch a server (which would leave a process running
   the user might not know about).

## Promote / Edit on selection (optional)

When `--proposals-repo=OWNER/REPO` is set, every page in the served
viewer becomes interactive: highlighting any text in the rendered
markdown pops a small floating toolbar with two buttons.

**Promote** captures the selection verbatim and proposes it as new
content. Clicking it:

1. Captures the selection, source-page path, page title, and
   surrounding block (paragraph / list item / heading)
2. POSTs `{kind: "promote", selection, source_path, ...}` to
   `/api/promote`
3. The server clones (or updates) the proposals-repo checkout, writes
   `proposals/<timestamp>-promote-<slug>.md`, pushes a
   `promote/<timestamp>-<slug>` branch, runs `gh pr create`
4. The PR URL is shown in a toast at the bottom-right of the viewer

**Edit** opens a small modal pre-filled with the selection. The user
tweaks the wording and clicks Submit. The modal POSTs
`{kind: "edit", original, proposed, source_path, ...}` to
`/api/promote`; the proposal file then has both an `## Original` and
`## Proposed` block, and the branch / PR title use `Edit:` rather than
`Promote:`. Submit is disabled if the proposed text is empty or
identical to the original.

The proposals repo is intentionally an **inbox** — an offline job
elsewhere is expected to consume `proposals/*.md` files and apply them
as incremental updates to the canonical wiki. See
[oscarkang24/wiki-proposals](https://github.com/oscarkang24/wiki-proposals)
README for both file shapes.

Failure modes worth flagging to the user:
- `gh` not installed or not authenticated for the proposals repo
- The repo doesn't exist (the server returns 500; clone step fails)
- Port already in use (server fails to start)

## Reference files

- [scripts/serve_wiki.sh](scripts/serve_wiki.sh) — orchestrates build + serve
- [scripts/build_html_site.py](scripts/build_html_site.py) — markdown → HTML site generator for all 5 tabs (also injects Edit / Promote / Gaps-panel JS)
- [scripts/scan_candidates.py](scripts/scan_candidates.py) — cluster-mode + ticket-mode candidate generator (invoked from `/api/rescan` and `/api/scan-from-ticket`)
- [scripts/score_candidates.py](scripts/score_candidates.py) — computes `bridge_score` for each candidate against each customer's `GAPS.json`; runs after every rescan
- [scripts/promote_server.py](scripts/promote_server.py) — static-files server + the `POST /api/*` handlers (`promote`, `rescan`, `scan-from-ticket`, `create-skill`, `promote-skill`, `acknowledge-drift`, `rescan-drift`)
- [README.md](README.md) — install + manual usage
