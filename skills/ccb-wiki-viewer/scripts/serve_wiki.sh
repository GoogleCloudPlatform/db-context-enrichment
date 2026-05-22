#!/usr/bin/env bash
# serve_wiki.sh — build an HTML viewer for a customer-context wiki and serve
# it on a local port. The parameterized form of the repo's try.sh demo.
#
# Usage:
#   bash serve_wiki.sh [--wiki-dir=PATH] [--site-dir=PATH] [--port=N] [--no-open] \
#                      [--data-dir=PATH] \
#                      [--bootstrap-tabs] [--customer-name=NAME] [--wiki-name=NAME] \
#                      [--proposals-repo=OWNER/REPO] [--proposals-checkout=PATH]
#
# Defaults:
#   --wiki-dir            auto-detect: first customer under ./customer-context/wikis/,
#                         then ./customer-context/context/ (legacy), then ./examples/sample_output/
#   --site-dir            <wiki-dir>/../site
#   --port                8765
#   --data-dir            auto-detect context-center root above <wiki-dir>; empty otherwise
#   --bootstrap-tabs      off — when on, synthesize a context-center root with empty
#                         tickets/candidates/skills/drift dirs so all 5 tabs render
#                         even when the wiki isn't already in context-center layout
#   --customer-name       basename of --wiki-dir (only used with --bootstrap-tabs)
#   --wiki-name           same as --customer-name (only used with --bootstrap-tabs)
#   --proposals-repo      (none → Promote button is non-functional; static-only mode)
#   --proposals-checkout  ~/.cache/wiki-proposals
#
# Environment:
#   BIND                  bind address for the server. Default 127.0.0.1 (loopback
#                         only). Set BIND=0.0.0.0 to accept connections from other
#                         devices on your LAN / tailnet.
#
# Notes on action endpoints:
#   This script always runs promote_server.py (not the bare http.server) so the
#   GET/static parts of the viewer work identically in either mode. The action
#   endpoints (rescan, scan-from-ticket, create-skill, rescan-drift,
#   acknowledge-drift, promote-skill) are only enabled when the relevant flags
#   are passed. We auto-detect --data-dir when --wiki-dir lives inside a
#   context-center layout (i.e. .../wikis/<customer>/<wiki-name>); otherwise the
#   five --data-dir-gated endpoints return 503 — the static viewer still works.
#
# Notes on --bootstrap-tabs:
#   In single-wiki mode only the Wikis tab renders, because the other four
#   sections (Tickets, Candidates, Skills, Drift) are sibling subdirs of a
#   context-center root that isn't there. --bootstrap-tabs synthesizes that
#   root in a sibling .cc-bootstrap/ dir: the wiki is copied under
#   wikis/<customer>/<wiki-name>/ and empty placeholder dirs are created for
#   the other four sections, so all 5 tabs render (the empty ones show
#   "No items yet"). The bootstrap dir is regenerated on each run; the
#   original --wiki-dir is never modified.
#
#   We copy rather than symlink because Python <3.13's pathlib.rglob doesn't
#   follow directory symlinks, so a symlinked wiki would render as empty.
#   For typical wiki sizes (a few MB) the copy is sub-second.
#
# Stop the server with Ctrl-C, or `lsof -ti :PORT | xargs kill`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIKI_DIR=""
SITE_DIR=""
DATA_DIR=""
PORT="8765"
BIND="${BIND:-127.0.0.1}"
OPEN_BROWSER=true
PROPOSALS_REPO=""
PROPOSALS_CHECKOUT="$HOME/.cache/wiki-proposals"
BOOTSTRAP_TABS=false
BOOTSTRAP_CUSTOMER=""
BOOTSTRAP_WIKI_NAME=""

# --- Parse args ---

for arg in "$@"; do
  case "$arg" in
    --wiki-dir=*)             WIKI_DIR="${arg#*=}" ;;
    --site-dir=*)             SITE_DIR="${arg#*=}" ;;
    --data-dir=*)             DATA_DIR="${arg#*=}" ;;
    --port=*)                 PORT="${arg#*=}" ;;
    --no-open)                OPEN_BROWSER=false ;;
    --bootstrap-tabs)         BOOTSTRAP_TABS=true ;;
    --customer-name=*)        BOOTSTRAP_CUSTOMER="${arg#*=}" ;;
    --wiki-name=*)            BOOTSTRAP_WIKI_NAME="${arg#*=}" ;;
    --proposals-repo=*)       PROPOSALS_REPO="${arg#*=}" ;;
    --proposals-checkout=*)   PROPOSALS_CHECKOUT="${arg#*=}" ;;
    -h|--help)
      sed -n '2,45p' "$0"
      exit 0
      ;;
    *)
      echo "error: unknown arg $arg" >&2
      exit 2
      ;;
  esac
done

# --- Auto-detect wiki dir if not given ---
#
# Preferred (new layout): builder writes ./customer-context/wikis/<customer>/.
# Pick the first customer subdir that has .md files; the rest of the wiki-viewer
# walks up via --data-dir auto-detection and renders all 5 tabs.
# Falls back to legacy ./customer-context/context/ (pre-wikis/ layout) and the
# bundled sample.

if [ -z "$WIKI_DIR" ]; then
  for data_root in "./customer-context" "./examples/sample_context_center"; do
    if [ -d "$data_root/wikis" ]; then
      first_wiki="$(find "$data_root/wikis" -mindepth 1 -maxdepth 1 -type d | sort | head -n 1)"
      if [ -n "$first_wiki" ] && find "$first_wiki" -name '*.md' -print -quit | grep -q .; then
        WIKI_DIR="$first_wiki"
        echo "==> Auto-detected wiki at $WIKI_DIR" >&2
        break
      fi
    fi
  done
fi

if [ -z "$WIKI_DIR" ]; then
  for candidate in "./customer-context/context" "./examples/sample_output"; do
    if [ -d "$candidate" ] && find "$candidate" -name '*.md' -print -quit | grep -q .; then
      WIKI_DIR="$candidate"
      echo "==> Auto-detected wiki at $WIKI_DIR (legacy layout)" >&2
      break
    fi
  done
fi

if [ -z "$WIKI_DIR" ]; then
  echo "error: no --wiki-dir given and no wiki found at the standard locations" >&2
  echo "       (./customer-context/wikis/<customer>/, ./customer-context/context/," >&2
  echo "        ./examples/sample_output/)" >&2
  echo "       pass an explicit --wiki-dir=PATH." >&2
  exit 2
fi

if [ ! -d "$WIKI_DIR" ]; then
  echo "error: --wiki-dir=$WIKI_DIR is not a directory" >&2
  exit 2
fi

if ! find "$WIKI_DIR" -name '*.md' -print -quit | grep -q .; then
  echo "error: $WIKI_DIR contains no .md files; nothing to serve" >&2
  exit 2
fi

# Default site dir: sibling "site/" of the wiki dir
if [ -z "$SITE_DIR" ]; then
  SITE_DIR="$(dirname "$WIKI_DIR")/site"
fi

# --- Auto-detect context-center data dir ---
#
# The five action endpoints (rescan, scan-from-ticket, create-skill,
# rescan-drift, acknowledge-drift) all require a context-center root that
# contains wikis/, candidates/, tickets/ subdirs (see promote_server.py
# --data-dir).
#
# If --wiki-dir is itself nested inside such a layout (i.e. the path
# .../wikis/<customer>/<wiki-name>), we can auto-derive --data-dir as the
# grandparent of wikis/. Otherwise we leave DATA_DIR empty and those
# endpoints will return 503 — the static viewer still works.
if [ -z "$DATA_DIR" ]; then
  wiki_abs="$(cd "$WIKI_DIR" && pwd -P)"
  parent="$(dirname "$wiki_abs")"
  grandparent="$(dirname "$parent")"
  # Expect: wiki = .../<data-dir>/wikis/<customer>/<wiki-name>
  if [ "$(basename "$(dirname "$parent")")" = "wikis" ]; then
    candidate_data="$(dirname "$(dirname "$parent")")"
    if [ -d "$candidate_data/wikis" ]; then
      DATA_DIR="$candidate_data"
      echo "==> Auto-detected context-center data dir at $DATA_DIR" >&2
    fi
  elif [ "$(basename "$parent")" = "wikis" ] && [ -d "$grandparent/wikis" ]; then
    # Path = .../<data-dir>/wikis/<wiki-name>
    DATA_DIR="$grandparent"
    echo "==> Auto-detected context-center data dir at $DATA_DIR" >&2
  fi
fi

if [ -n "$DATA_DIR" ] && [ ! -d "$DATA_DIR" ]; then
  echo "error: --data-dir=$DATA_DIR is not a directory" >&2
  exit 2
fi

# --- Bootstrap context-center layout (--bootstrap-tabs) ---
#
# When the wiki isn't already in a context-center layout, synthesize one in a
# sibling .cc-bootstrap/ dir so all 5 tabs render. The wiki is symlinked under
# wikis/<customer>/<wiki-name>/ — the original --wiki-dir is never modified.
# Skipped (with a note) if --data-dir was already given or auto-detected.

if [ "$BOOTSTRAP_TABS" = true ]; then
  if [ -n "$DATA_DIR" ]; then
    echo "==> --bootstrap-tabs ignored — already in context-center layout (data-dir=$DATA_DIR)" >&2
  else
    wiki_abs="$(cd "$WIKI_DIR" && pwd -P)"
    wiki_basename="$(basename "$wiki_abs")"
    customer="${BOOTSTRAP_CUSTOMER:-$wiki_basename}"
    wiki_name="${BOOTSTRAP_WIKI_NAME:-$wiki_basename}"
    bootstrap_root="$(dirname "$SITE_DIR")/.cc-bootstrap"
    rm -rf "$bootstrap_root"
    mkdir -p \
      "$bootstrap_root/wikis/$customer" \
      "$bootstrap_root/tickets" \
      "$bootstrap_root/candidates" \
      "$bootstrap_root/skills" \
      "$bootstrap_root/drift"
    cp -R "$wiki_abs" "$bootstrap_root/wikis/$customer/$wiki_name"
    DATA_DIR="$bootstrap_root"
    echo "==> Bootstrapped context-center layout at $bootstrap_root" >&2
    echo "    wiki copied to wikis/$customer/$wiki_name (from $wiki_abs)" >&2
    echo "    placeholder dirs: tickets/ candidates/ skills/ drift/ (will render as 'No items yet')" >&2
  fi
fi

# --- Sanity ---

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found. Install Python 3.9+: https://www.python.org/downloads/" >&2
  exit 1
fi

if command -v lsof >/dev/null 2>&1 && lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "error: port $PORT is already in use." >&2
  echo "  free it (lsof -ti :$PORT | xargs kill) or rerun with --port=N" >&2
  exit 1
fi

# --- Build ---
#
# In context-center mode (DATA_DIR detected), build from the data root so all
# sections (wikis/tickets/candidates/skills/drift) render as top tabs. In
# single-wiki mode, build from the wiki dir directly.

if [ -n "$DATA_DIR" ]; then
  BUILD_INPUT="$DATA_DIR"
else
  BUILD_INPUT="$WIKI_DIR"
fi

echo "==> Building HTML viewer: $BUILD_INPUT -> $SITE_DIR"
rm -rf "$SITE_DIR"
python3 "$SCRIPT_DIR/build_html_site.py" \
  --input-dir="$BUILD_INPUT" \
  --output-dir="$SITE_DIR" \
  --repo-name="Customer wiki — $(basename "$(cd "$WIKI_DIR" && pwd -P)")"

URL="http://127.0.0.1:$PORT/index.html"

# --- Open browser (best-effort) ---

if $OPEN_BROWSER; then
  (
    sleep 1
    if command -v open >/dev/null 2>&1; then        # macOS
      open "$URL" 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then  # Linux
      xdg-open "$URL" 2>/dev/null || true
    elif command -v wslview >/dev/null 2>&1; then   # WSL
      wslview "$URL" 2>/dev/null || true
    fi
  ) &
fi

echo ""
echo "==> Serving at $URL"
if [ "$BIND" != "127.0.0.1" ]; then
  echo "    bind=$BIND — also reachable from other devices on your network or tailnet"
fi
if [ -n "$PROPOSALS_REPO" ]; then
  echo "    Promote target: $PROPOSALS_REPO (checkout: $PROPOSALS_CHECKOUT)"
else
  echo "    Promote button is inert — pass --proposals-repo=OWNER/REPO to enable it."
fi
if [ -n "$DATA_DIR" ]; then
  echo "    Action endpoints enabled (data-dir=$DATA_DIR)"
else
  echo "    Action endpoints (rescan / scan-from-ticket / create-skill / rescan-drift /"
  echo "    acknowledge-drift) will 503 — pass --data-dir=PATH to a context-center root"
  echo "    (containing wikis/, candidates/, tickets/) to enable them."
fi
echo "    Ctrl-C to stop, or: lsof -ti :$PORT | xargs kill"
echo ""

# Always run promote_server.py (never bare http.server) so the static viewer
# behaves identically across modes. Endpoints gate themselves on the relevant
# flags inside promote_server.py.
if [ -n "$PROPOSALS_REPO" ] && ! command -v gh >/dev/null 2>&1; then
  echo "error: --proposals-repo set but 'gh' CLI not found. Install: https://cli.github.com" >&2
  exit 1
fi

EXTRA_ARGS=()
if [ -n "$PROPOSALS_REPO" ]; then
  EXTRA_ARGS+=(--proposals-repo="$PROPOSALS_REPO" --proposals-checkout="$PROPOSALS_CHECKOUT")
fi
if [ -n "$DATA_DIR" ]; then
  EXTRA_ARGS+=(--data-dir="$DATA_DIR")
fi

# `${arr[@]+"${arr[@]}"}` safely expands to nothing when the array is empty,
# instead of tripping `set -u`'s unbound-variable check.
exec python3 "$SCRIPT_DIR/promote_server.py" \
  --site-dir="$SITE_DIR" \
  --port="$PORT" \
  --bind="$BIND" \
  ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
