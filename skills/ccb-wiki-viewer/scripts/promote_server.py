#!/usr/bin/env python3
"""Serve a built wiki/context-center site with optional POST endpoints.

This replaces `python3 -m http.server` for the wiki-viewer skill. Static
file serving is identical to `SimpleHTTPRequestHandler`; the added
behavior is seven POST endpoints:

  POST /api/promote (only if --proposals-repo is set)
    1. Receives JSON: {selection, source_path, page_title, surrounding_context, page_url}
    2. Locates a checkout of the proposals repo (clones if missing, fetches
       and resets to origin/main if present)
    3. Writes proposals/<timestamp>-<slug>.md with frontmatter + body
    4. Pushes a `promote/<timestamp>-<slug>` branch and runs `gh pr create`
    5. Returns {pr_url}

  POST /api/rescan (only if --data-dir is set)
    1. Runs scan_candidates.py against <data-dir>/wikis, writing
       <data-dir>/candidates/
    2. Re-runs build_html_site.py to rebuild --site-dir from --data-dir
    3. Returns {candidate_count}

  POST /api/scan-from-ticket (only if --data-dir is set)
    1. Receives JSON: {ticket_path}
    2. Runs scan_candidates.py --ticket-file=<path> against the wikis;
       output is appended to <data-dir>/candidates/
    3. Re-runs build_html_site.py
    4. Returns {candidate_slug, candidate_url}

  POST /api/promote-skill (requires --data-dir AND --proposals-repo)
    1. Receives JSON: {skill_path}
    2. Copies <data-dir>/<skill_path>/ into the proposals repo at
       proposals/skills/<slug>/
    3. Pushes a `promote-skill/<timestamp>-<slug>` branch and opens a PR
    4. Returns {pr_url}

  POST /api/create-skill (only if --data-dir is set)
    1. Receives JSON: {candidate_path}
    2. Reads <data-dir>/<candidate_path> + sibling sources.json
    3. Runs `claude -p --dangerously-skip-permissions "<skill-creator prompt>"`
       so the skill-creator skill scaffolds a real skill into
       <data-dir>/skills/<slug>/
    4. Re-runs build_html_site.py
    5. Returns {skill_path, skill_url}

  POST /api/rescan-drift (only if --data-dir is set)
    1. Receives JSON: {customer} (the wiki sub-directory to re-scan)
    2. Re-runs source_diff.py + revalidate_drift.py for that customer
    3. Re-runs build_html_site.py to refresh the Drift tab
    4. Returns {drift_count}

  POST /api/acknowledge-drift (only if --data-dir is set)
    1. Receives JSON: {customer, drift_id, note?}
    2. Shells out to acknowledge_drift.py to append the entry to
       <wiki-root>/.drift-acknowledged.json
    3. Re-runs build_html_site.py so the entry disappears from the tab
    4. Returns {ok: true}

Args (env vars or CLI):
  --site-dir              the built HTML site to serve (required)
  --port                  local port (default 8765)
  --proposals-repo        GitHub slug, e.g. oscarkang24/wiki-proposals (optional)
  --proposals-checkout    local clone path (default ~/.cache/wiki-proposals)
  --data-dir              context-center data root (parent of wikis/, candidates/, etc.) (optional)
  --repo-name             passed through to build_html_site.py during rescan
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, check: bool = True,
        env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True, env=env)


def slugify(text: str, max_len: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "promotion").rstrip("-")


def ensure_checkout(repo_slug: str, checkout_dir: Path) -> None:
    """Clone the proposals repo if missing; otherwise fetch+reset to origin/main."""
    if not checkout_dir.exists():
        checkout_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["gh", "repo", "clone", repo_slug, str(checkout_dir)])
        return
    # Existing checkout — make sure we're on a clean main matching origin
    run(["git", "fetch", "--quiet", "origin"], cwd=checkout_dir)
    run(["git", "checkout", "--quiet", "main"], cwd=checkout_dir)
    run(["git", "reset", "--hard", "--quiet", "origin/main"], cwd=checkout_dir)
    # Best-effort: delete any lingering local promote/*, edit/*, promote-skill/*
    # branches that were already pushed (so they don't accumulate). Don't fail on errors.
    for prefix in ("promote/*", "edit/*", "promote-skill/*"):
        branches = run(["git", "branch", "--list", prefix], cwd=checkout_dir, check=False)
        for line in branches.stdout.splitlines():
            b = line.strip().lstrip("*").strip()
            if b:
                subprocess.run(["git", "branch", "-D", b], cwd=checkout_dir, capture_output=True)


def make_proposal(payload: dict, checkout_dir: Path, repo_slug: str) -> str:
    kind = (payload.get("kind") or "promote").strip().lower()
    if kind not in ("promote", "edit"):
        raise ValueError(f"unknown kind: {kind!r} (expected 'promote' or 'edit')")
    source_path = (payload.get("source_path") or "").strip()
    page_title = (payload.get("page_title") or source_path or "untitled").strip()
    context = (payload.get("surrounding_context") or "").strip()
    page_url = (payload.get("page_url") or "").strip()
    if not source_path:
        raise ValueError("missing source_path")

    if kind == "promote":
        selection = (payload.get("selection") or "").strip()
        if not selection:
            raise ValueError("empty selection")
        original = None
        proposed = selection
    else:  # edit
        original = (payload.get("original") or "").strip()
        proposed = (payload.get("proposed") or "").strip()
        if not original:
            raise ValueError("edit: missing original")
        if not proposed:
            raise ValueError("edit: missing proposed")
        if original == proposed:
            raise ValueError("edit: proposed is identical to original")

    ts = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    slug = slugify(page_title)
    filename = f"{ts}-{kind}-{slug}.md"
    branch = f"{kind}/{ts}-{slug}"

    # Frontmatter
    today = dt.date.today().isoformat()
    user = os.environ.get("USER", "unknown")
    body_lines = [
        "---",
        f"kind: {kind}",
        f"source_page: {source_path}",
        f"source_url: {page_url}",
        f"selected_on: {today}",
        f"selected_by: {user}",
        f"page_title: {json.dumps(page_title)}",
        "---",
        "",
        "**Surrounding context:**",
        "",
    ]
    if context:
        for line in context.splitlines():
            body_lines.append(f"> {line}")
    else:
        body_lines.append("> _(no surrounding block detected)_")
    body_lines += ["", "---", ""]

    if kind == "promote":
        body_lines += [proposed, ""]
    else:  # edit
        body_lines += [
            "## Original",
            "",
            original,
            "",
            "## Proposed",
            "",
            proposed,
            "",
        ]
    file_body = "\n".join(body_lines)

    # Write + commit + push + PR
    proposals_dir = checkout_dir / "proposals"
    proposals_dir.mkdir(exist_ok=True)
    file_rel = f"proposals/{filename}"
    (checkout_dir / file_rel).write_text(file_body, encoding="utf-8")

    run(["git", "checkout", "--quiet", "-b", branch], cwd=checkout_dir)
    run(["git", "add", file_rel], cwd=checkout_dir)
    verb = "Promote" if kind == "promote" else "Edit"
    commit_msg = f"{verb}: {page_title[:60]}"
    run(["git", "commit", "--quiet", "-m", commit_msg], cwd=checkout_dir)
    run(["git", "push", "--quiet", "-u", "origin", branch], cwd=checkout_dir)

    # PR body: short pointer-style, all the content lives in the committed file
    if kind == "promote":
        pr_body = (
            f"Promoted from `{source_path}` in the LLM wiki.\n\n"
            f"Source page: {page_url or '_(no live URL)_' }\n\n"
            f"See [`{file_rel}`](../blob/{branch}/{file_rel}) for the selection + context."
        )
    else:
        pr_body = (
            f"Edit proposed against `{source_path}` in the LLM wiki.\n\n"
            f"Source page: {page_url or '_(no live URL)_' }\n\n"
            f"See [`{file_rel}`](../blob/{branch}/{file_rel}) for the original + proposed text + context."
        )
    pr_title = f"{verb}: {page_title[:60]}"
    pr_res = run(
        ["gh", "pr", "create", "--repo", repo_slug, "--head", branch, "--base", "main",
         "--title", pr_title, "--body", pr_body],
        cwd=checkout_dir,
    )
    pr_url = pr_res.stdout.strip().splitlines()[-1]

    # Reset back to main so the next promote starts clean
    run(["git", "checkout", "--quiet", "main"], cwd=checkout_dir)
    return pr_url


def best_error_line(stderr: str | None, stdout: str | None) -> str:
    """Extract a useful one-line summary from a failed subprocess.

    Prefers the last non-trivial line of stderr (skipping empty lines and
    pure prefix labels like "stderr:"). Falls back to stdout, then a generic
    message. Cap at 240 chars so it fits in a toast.
    """
    for blob in (stderr, stdout):
        if not blob:
            continue
        for line in reversed(blob.splitlines()):
            s = line.strip()
            if not s:
                continue
            if s.lower() in ("stdout:", "stderr:"):
                continue
            return s[:240]
    return "subprocess failed (no output)"


def promote_skill(skill_dir: Path,
                  data_dir: Path,
                  checkout_dir: Path,
                  repo_slug: str) -> str:
    """Copy a skill's whole directory to the proposals repo and open a PR.

    Files land at proposals/skills/<slug>/<...> in the proposals repo, on a
    branch named promote-skill/<timestamp>-<slug>.
    """
    slug = skill_dir.name
    if not (skill_dir / "SKILL.md").is_file():
        raise RuntimeError(f"skill dir is missing SKILL.md: {skill_dir}")

    ensure_checkout(repo_slug, checkout_dir)

    ts = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    branch = f"promote-skill/{ts}-{slug}"
    target_subdir = checkout_dir / "proposals" / "skills" / slug
    if target_subdir.exists():
        # Stale leftover from a prior failed run — remove so the copy is clean.
        import shutil as _shutil
        _shutil.rmtree(target_subdir)
    target_subdir.parent.mkdir(parents=True, exist_ok=True)

    # Copy the entire skill dir.
    import shutil as _shutil
    _shutil.copytree(skill_dir, target_subdir)

    rel_paths = []
    for p in sorted(target_subdir.rglob("*")):
        if p.is_file():
            rel_paths.append(p.relative_to(checkout_dir).as_posix())
    if not rel_paths:
        raise RuntimeError(f"no files copied from {skill_dir}")

    run(["git", "checkout", "--quiet", "-b", branch], cwd=checkout_dir)
    run(["git", "add"] + rel_paths, cwd=checkout_dir)
    commit_msg = f"Skill: {slug}"
    run(["git", "commit", "--quiet", "-m", commit_msg], cwd=checkout_dir)
    run(["git", "push", "--quiet", "-u", "origin", branch], cwd=checkout_dir)

    pr_body = (
        f"Promoting skill `{slug}` from local skills/ dir.\n\n"
        f"Files: {len(rel_paths)} (including `proposals/skills/{slug}/SKILL.md`).\n\n"
        "Generated by the context-center viewer's Promote-skill button "
        "(local skills dir → proposals repo)."
    )
    pr_title = f"Skill: {slug}"
    pr_res = run(
        ["gh", "pr", "create", "--repo", repo_slug, "--head", branch, "--base", "main",
         "--title", pr_title, "--body", pr_body],
        cwd=checkout_dir,
    )
    pr_url = pr_res.stdout.strip().splitlines()[-1]

    run(["git", "checkout", "--quiet", "main"], cwd=checkout_dir)
    return pr_url


def _claude_env() -> dict:
    """Env for shelling out to `claude -p`. When the parent itself is a
    Claude Code session, strip CLAUDECODE + host-managed auth + every
    CLAUDE_CODE_*/CLAUDE_AGENT_* sentinel so the nested call falls back to
    the user's stored OAuth credentials."""
    env = dict(os.environ)
    if env.get("CLAUDECODE"):
        for k in list(env.keys()):
            if (
                k in ("CLAUDECODE", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")
                or k.startswith("CLAUDE_CODE_")
                or k.startswith("CLAUDE_AGENT_")
            ):
                env.pop(k, None)
    return env


def run_create_skill(data_dir: Path, site_dir: Path, repo_name: str,
                     candidate_path: str) -> dict:
    """Run `/skill-creator` headlessly to promote a candidate into a real skill.

    Reads the candidate's candidate.md + sources.json, builds a prompt that
    tells Claude to use skill-creator and write into <data-dir>/skills/<slug>/,
    runs `claude -p` with --dangerously-skip-permissions, then rebuilds the
    site so the new skill appears in the Skills tab.
    """
    # Validate candidate_path: must live under data-dir/candidates/<id>/candidate.md
    candidate_abs = (data_dir / candidate_path).resolve()
    candidates_root = (data_dir / "candidates").resolve()
    if not str(candidate_abs).startswith(str(candidates_root) + os.sep):
        raise RuntimeError(f"candidate_path must be under candidates/: {candidate_path}")
    if candidate_abs.name != "candidate.md" or not candidate_abs.is_file():
        raise RuntimeError(f"not a candidate.md file: {candidate_path}")

    candidate_dir = candidate_abs.parent
    slug = candidate_dir.name
    candidate_md = candidate_abs.read_text(encoding="utf-8")
    sources_json_path = candidate_dir / "sources.json"
    sources_text = sources_json_path.read_text(encoding="utf-8") if sources_json_path.exists() else "{}"

    skills_root = data_dir / "skills"
    skills_root.mkdir(exist_ok=True)
    target_dir = skills_root / slug

    prompt = (
        "Use the skill-creator skill to scaffold a new Claude Code skill from the "
        "candidate stub below. Write the skill files into the target directory shown.\n\n"
        f"Target directory (create if missing): {target_dir}\n"
        "Required output: at minimum SKILL.md inside the target dir. Add a scripts/ "
        "subdir with any obvious helper scripts the skill needs. DO NOT run evals or "
        "tests — this is a one-shot scaffolding pass, not an interactive build. Stop "
        "as soon as the SKILL.md is written.\n\n"
        f"Candidate name (slug): {slug}\n\n"
        "## Candidate stub (candidate.md)\n\n"
        f"{candidate_md}\n\n"
        "## Source references (sources.json)\n\n"
        "```json\n"
        f"{sources_text}\n"
        "```\n\n"
        "Improve the draft SKILL.md where skill-creator's best practices suggest "
        "changes (clearer description for trigger accuracy, sharper when-to-use, "
        "concrete inputs/outputs)."
    )

    cmd = [
        "claude", "-p",
        "--dangerously-skip-permissions",
        prompt,
    ]
    sys.stderr.write(f"==> Create-skill: invoking claude -p (target: {target_dir})\n")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_claude_env())
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude -p failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )

    skill_md = target_dir / "SKILL.md"
    if not skill_md.exists():
        raise RuntimeError(
            f"claude -p completed but no SKILL.md was written at {skill_md}.\n"
            f"stdout tail: {proc.stdout[-500:]}"
        )

    # Rebuild the site so the new skill appears in the Skills tab.
    scripts_dir = Path(__file__).resolve().parent
    build_script = scripts_dir / "build_html_site.py"
    sys.stderr.write(f"==> Create-skill: rebuilding site at {site_dir}\n")
    run([sys.executable, str(build_script),
         f"--input-dir={data_dir}",
         f"--output-dir={site_dir}",
         f"--repo-name={repo_name}"], env=_claude_env())

    skill_rel = target_dir.relative_to(data_dir).as_posix()
    return {
        "skill_path": skill_rel,
        "skill_url": f"/{skill_rel}/SKILL.html",
    }


def _maybe_score_candidates(scripts_dir: Path, wikis_root: Path,
                            candidates_dir: Path, env: dict) -> None:
    """Run score_candidates.py if it exists. Tolerant of failure — bridge
    scoring is enrichment, not a blocking step. If wikis don't have GAPS.json
    yet, the scorer will write bridge_score=0 for every candidate, which is
    fine."""
    score_script = scripts_dir / "score_candidates.py"
    if not score_script.is_file():
        return
    try:
        run([sys.executable, str(score_script),
             f"--wikis-root={wikis_root}",
             f"--candidates-dir={candidates_dir}",
             "--quiet"], env=env)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            f"warning: score_candidates failed (continuing): "
            f"{best_error_line(e.stderr, e.stdout)}\n"
        )


def run_scan_from_ticket(data_dir: Path, site_dir: Path, repo_name: str,
                         ticket_path: str) -> dict:
    """Run scan_candidates.py with --ticket-file to synthesize ONE candidate
    from a single ticket + the wikis. Append (don't wipe) the candidates dir.
    Rebuild the site. Returns {candidate_slug, candidate_url, used_canned}.

    Demo fallback: if the live `claude -p` call fails (e.g. nested Claude Code
    auth) AND the ticket has a sibling canned_response.txt, retry the scan
    with --response-file pointing at that fixture so the demo still works.
    """
    scripts_dir = Path(__file__).resolve().parent
    scan_script = scripts_dir / "scan_candidates.py"
    build_script = scripts_dir / "build_html_site.py"

    # Validate ticket_path lives under data-dir/tickets/<id>/ticket.md
    ticket_abs = (data_dir / ticket_path).resolve()
    tickets_root = (data_dir / "tickets").resolve()
    if not str(ticket_abs).startswith(str(tickets_root) + os.sep):
        raise RuntimeError(f"ticket_path must be under tickets/: {ticket_path}")
    if ticket_abs.name != "ticket.md" or not ticket_abs.is_file():
        raise RuntimeError(f"not a ticket.md file: {ticket_path}")

    wikis_root = data_dir / "wikis"
    candidates_dir = data_dir / "candidates"
    if not wikis_root.is_dir():
        raise RuntimeError(f"--data-dir/wikis not found: {wikis_root}")

    env = _claude_env()
    sys.stderr.write(f"==> Scan-from-ticket: {ticket_abs.parent.name}\n")

    base_args = [sys.executable, str(scan_script),
                 f"--wikis-root={wikis_root}",
                 f"--output-dir={candidates_dir}",
                 f"--ticket-file={ticket_abs}"]
    canned_path = ticket_abs.parent / "canned_response.txt"
    used_canned = False
    try:
        proc = run(base_args, env=env)
    except subprocess.CalledProcessError as live_err:
        if canned_path.is_file():
            sys.stderr.write(
                f"==> Scan-from-ticket: live claude -p failed, falling back to "
                f"{canned_path.name} (demo mode)\n"
            )
            proc = run(base_args + [f"--response-file={canned_path}"], env=env)
            used_canned = True
        else:
            raise live_err

    new_slugs = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if not new_slugs:
        raise RuntimeError("scan_candidates.py wrote no new candidate (empty stdout)")
    new_slug = new_slugs[-1]

    # Score the new candidate (and any existing ones) by gap-bridging value.
    _maybe_score_candidates(scripts_dir, wikis_root, candidates_dir, env)

    sys.stderr.write(f"==> Scan-from-ticket: rebuilding site at {site_dir}\n")
    run([sys.executable, str(build_script),
         f"--input-dir={data_dir}",
         f"--output-dir={site_dir}",
         f"--repo-name={repo_name}"], env=env)

    return {
        "candidate_slug": new_slug,
        "candidate_url": f"/candidates/{new_slug}/candidate.html",
        "used_canned": used_canned,
    }


def find_wiki_root_for_customer(data_dir: Path, customer: str) -> Path | None:
    """Walk wikis/<customer>/ to find the directory that contains source_manifest.json.

    Mirrors find_wiki_root in build_html_site.py — handles both flat layouts
    (wikis/<customer>/source_manifest.json) and nested ones
    (wikis/<customer>/<subdir>/source_manifest.json) without hardcoding depth.
    """
    customer_root = data_dir / "wikis" / customer
    if not customer_root.is_dir():
        return None
    # BFS for the deepest source_manifest.json.
    stack = [customer_root]
    while stack:
        cur = stack.pop()
        if (cur / "source_manifest.json").is_file():
            return cur
        for child in cur.iterdir():
            if child.is_dir():
                stack.append(child)
    return None


def find_ccb_scripts() -> Path:
    """Resolve customer-context-builder/scripts/ relative to this skill dir.

    The two skills live as siblings under skills/, so we walk up from
    skills/wiki-viewer/scripts/ to skills/ and then back down. This also
    works when wiki-viewer is symlinked into ~/.claude/skills/ — Path
    resolution follows the symlink to the real location.
    """
    here = Path(__file__).resolve().parent
    skills_root = here.parent.parent  # skills/ dir
    candidate = skills_root / "customer-context-builder" / "scripts"
    if candidate.is_dir():
        return candidate
    # Fallback: relative to repo root if running uninstalled.
    repo_candidate = Path.cwd() / "skills" / "customer-context-builder" / "scripts"
    if repo_candidate.is_dir():
        return repo_candidate
    raise RuntimeError(
        "couldn't locate customer-context-builder/scripts/; "
        f"tried {candidate} and {repo_candidate}"
    )


def stage_drift_artifacts(data_dir: Path) -> int:
    """Copy each customer wiki's DRIFT.md + DRIFT.json into <data-dir>/drift/<customer>/.

    Returns the number of customers staged. The Drift tab in the viewer reads
    from this staging dir (matches the section-per-top-level-dir pattern).
    """
    import shutil
    drift_root = data_dir / "drift"
    drift_root.mkdir(exist_ok=True)
    wikis_root = data_dir / "wikis"
    if not wikis_root.is_dir():
        return 0
    n = 0
    for customer_dir in sorted(wikis_root.iterdir()):
        if not customer_dir.is_dir():
            continue
        wiki_root = find_wiki_root_for_customer(data_dir, customer_dir.name)
        if wiki_root is None or not (wiki_root / "DRIFT.md").is_file():
            continue
        target = drift_root / customer_dir.name
        target.mkdir(exist_ok=True)
        shutil.copy2(wiki_root / "DRIFT.md", target / "DRIFT.md")
        if (wiki_root / "DRIFT.json").is_file():
            shutil.copy2(wiki_root / "DRIFT.json", target / "DRIFT.json")
        n += 1
    return n


def run_rescan_drift(data_dir: Path, site_dir: Path, repo_name: str,
                     customer: str) -> dict:
    """Re-run claims_sidecar + build_manifest + dep_graph + source_diff for one
    customer, then re-stage DRIFT.md into drift/<customer>/ and rebuild the site.

    We re-run the full upstream pipeline because source_diff's severity rules
    depend on claims_index.json (which sources are cited as EXTRACTED, etc.) —
    a fresh sidecar pass keeps drift severity in sync with current narrative state.
    """
    wiki_root = find_wiki_root_for_customer(data_dir, customer)
    if wiki_root is None:
        raise RuntimeError(f"no wiki root found for customer: {customer}")
    ccb = find_ccb_scripts()

    sys.stderr.write(f"==> Re-scan drift: {wiki_root}\n")
    # NOTE: we do NOT regenerate source_manifest.json here — that would erase
    # the baseline source_diff is comparing against. Only run claims/dep_graph
    # and then source_diff against the existing manifest.
    run([sys.executable, str(ccb / "claims_sidecar.py"),
         f"--wiki-root={wiki_root}", "--quiet"], check=False)
    run([sys.executable, str(ccb / "dep_graph.py"),
         f"--wiki-root={wiki_root}", "--quiet"])
    proc = subprocess.run(
        [sys.executable, str(ccb / "source_diff.py"),
         f"--wiki-root={wiki_root}", "--quiet"],
        capture_output=True, text=True,
    )
    # source_diff.py exits 1 when HIGH-severity drift exists — that's success
    # for our purposes, just means there ARE drifts. Treat anything > 1 as a
    # real failure.
    if proc.returncode > 1:
        raise RuntimeError(
            f"source_diff failed (exit {proc.returncode}): "
            f"{proc.stderr[:500]}"
        )
    # Stage 2 re-validation: substring + anchor checks per claim. Tolerant of
    # failure since the cheap stack runs without GCP / LLM access.
    revalidate_script = ccb / "revalidate_drift.py"
    if revalidate_script.is_file():
        proc = subprocess.run(
            [sys.executable, str(revalidate_script),
             f"--wiki-root={wiki_root}", "--quiet"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            sys.stderr.write(
                f"warning: revalidate_drift failed (continuing): "
                f"{best_error_line(proc.stderr, proc.stdout)}\n"
            )

    n_staged = stage_drift_artifacts(data_dir)

    # Rebuild the HTML so the new DRIFT.md shows up in the tab.
    scripts_dir = Path(__file__).resolve().parent
    build_script = scripts_dir / "build_html_site.py"
    sys.stderr.write(f"==> Re-scan drift: rebuilding site at {site_dir}\n")
    run([sys.executable, str(build_script),
         f"--input-dir={data_dir}",
         f"--output-dir={site_dir}",
         f"--repo-name={repo_name}"])

    # Pull a brief summary from the regenerated DRIFT.json so the toast
    # is informative.
    summary = "drift refreshed"
    drift_json = wiki_root / "DRIFT.json"
    if drift_json.is_file():
        try:
            d = json.loads(drift_json.read_text(encoding="utf-8"))
            kinds = d.get("by_kind", {})
            sevs = d.get("by_severity", {})
            summary = (
                f"{kinds.get('changed', 0)} changed · "
                f"{kinds.get('deleted', 0)} deleted · "
                f"{kinds.get('new', 0)} new "
                f"({sevs.get('high', 0)}H {sevs.get('medium', 0)}M "
                f"{sevs.get('low', 0)}L)"
            )
        except Exception:
            pass

    return {"summary": summary, "customers_staged": n_staged}


def run_acknowledge_drift(data_dir: Path, customer: str, drift_id: str) -> dict:
    """Append drift_id to the customer's .drift-acknowledged.json. Does NOT
    rebuild the site — the entry stays visible in the current view (with a
    visual line-through marker) until the next Re-scan."""
    wiki_root = find_wiki_root_for_customer(data_dir, customer)
    if wiki_root is None:
        raise RuntimeError(f"no wiki root found for customer: {customer}")
    ccb = find_ccb_scripts()

    sys.stderr.write(f"==> Ack drift {drift_id} for {customer}\n")
    proc = subprocess.run(
        [sys.executable, str(ccb / "acknowledge_drift.py"),
         f"--wiki-root={wiki_root}", f"--drift-id={drift_id}", "--quiet"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"acknowledge_drift.py failed (exit {proc.returncode}): "
            f"{proc.stderr[:500]}"
        )
    return {"acknowledged_id": drift_id, "customer": customer}


def run_rescan(data_dir: Path, site_dir: Path, repo_name: str) -> int:
    """Run scan_candidates.py + rebuild the HTML site. Returns candidate count."""
    scripts_dir = Path(__file__).resolve().parent
    scan_script = scripts_dir / "scan_candidates.py"
    build_script = scripts_dir / "build_html_site.py"

    wikis_root = data_dir / "wikis"
    candidates_dir = data_dir / "candidates"
    if not wikis_root.is_dir():
        raise RuntimeError(f"--data-dir/wikis not found: {wikis_root}")

    env = _claude_env()
    sys.stderr.write(f"==> Rescan: scanning {wikis_root}\n")
    run([sys.executable, str(scan_script),
         f"--wikis-root={wikis_root}",
         f"--output-dir={candidates_dir}"], env=env)

    # Score every candidate by gap-bridging value before rebuilding the site.
    _maybe_score_candidates(scripts_dir, wikis_root, candidates_dir, env)

    sys.stderr.write(f"==> Rescan: rebuilding site at {site_dir}\n")
    run([sys.executable, str(build_script),
         f"--input-dir={data_dir}",
         f"--output-dir={site_dir}",
         f"--repo-name={repo_name}"], env=env)

    # Count candidates by counting subdirs of candidates_dir.
    if not candidates_dir.is_dir():
        return 0
    return sum(1 for c in candidates_dir.iterdir() if c.is_dir())


def make_handler(site_dir: Path,
                 repo_slug: str | None,
                 checkout_dir: Path,
                 data_dir: Path | None,
                 repo_name: str):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def log_message(self, fmt, *args):
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

        def _send_json(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_promote(self):
            if not repo_slug:
                self._send_json(503, {"error": "promote disabled: server started without --proposals-repo"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            try:
                ensure_checkout(repo_slug, checkout_dir)
                pr_url = make_proposal(payload, checkout_dir, repo_slug)
                self._send_json(200, {"pr_url": pr_url})
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"promote failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"promote failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_rescan(self):
            if not data_dir:
                self._send_json(503, {"error": "rescan disabled: server started without --data-dir"})
                return
            try:
                count = run_rescan(data_dir, site_dir, repo_name)
                self._send_json(200, {"candidate_count": count})
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"rescan failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"rescan failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_scan_from_ticket(self):
            if not data_dir:
                self._send_json(503, {"error": "scan-from-ticket disabled: server started without --data-dir"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            ticket_path = (payload.get("ticket_path") or "").strip()
            if not ticket_path:
                self._send_json(400, {"error": "missing ticket_path"})
                return
            try:
                result = run_scan_from_ticket(data_dir, site_dir, repo_name, ticket_path)
                self._send_json(200, result)
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"scan-from-ticket failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"scan-from-ticket failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_create_skill(self):
            if not data_dir:
                self._send_json(503, {"error": "create-skill disabled: server started without --data-dir"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            candidate_path = (payload.get("candidate_path") or "").strip()
            if not candidate_path:
                self._send_json(400, {"error": "missing candidate_path"})
                return
            try:
                result = run_create_skill(data_dir, site_dir, repo_name, candidate_path)
                self._send_json(200, result)
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"create-skill failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"create-skill failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_promote_skill(self):
            if not data_dir:
                self._send_json(503, {"error": "promote-skill disabled: server started without --data-dir"})
                return
            if not repo_slug:
                self._send_json(503, {"error": "promote-skill disabled: set PROPOSALS_REPO and restart try.sh "
                                              "(or pass --proposals-repo to promote_server.py)"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            skill_path = (payload.get("skill_path") or "").strip()
            if not skill_path:
                self._send_json(400, {"error": "missing skill_path"})
                return
            # Validate skill_path is under data-dir/skills/.
            skill_abs = (data_dir / skill_path).resolve()
            skills_root = (data_dir / "skills").resolve()
            if not str(skill_abs).startswith(str(skills_root) + os.sep) or not skill_abs.is_dir():
                self._send_json(400, {"error": f"skill_path must be a directory under skills/: {skill_path}"})
                return
            try:
                pr_url = promote_skill(skill_abs, data_dir, checkout_dir, repo_slug)
                self._send_json(200, {"pr_url": pr_url})
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"promote-skill failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"promote-skill failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_rescan_drift(self):
            if not data_dir:
                self._send_json(503, {"error": "rescan-drift disabled: server started without --data-dir"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            customer = (payload.get("customer") or "").strip()
            if not customer:
                self._send_json(400, {"error": "missing customer"})
                return
            try:
                result = run_rescan_drift(data_dir, site_dir, repo_name, customer)
                self._send_json(200, result)
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"rescan-drift failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"rescan-drift failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def _handle_acknowledge_drift(self):
            if not data_dir:
                self._send_json(503, {"error": "acknowledge-drift disabled: server started without --data-dir"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
            except Exception as e:
                self._send_json(400, {"error": f"bad request: {e}"})
                return
            customer = (payload.get("customer") or "").strip()
            drift_id = (payload.get("drift_id") or "").strip()
            if not customer or not drift_id:
                self._send_json(400, {"error": "missing customer or drift_id"})
                return
            try:
                result = run_acknowledge_drift(data_dir, customer, drift_id)
                self._send_json(200, result)
            except subprocess.CalledProcessError as e:
                msg = best_error_line(e.stderr, e.stdout)
                sys.stderr.write(f"acknowledge-drift failed: {e.cmd}\nstdout: {e.stdout}\nstderr: {e.stderr}\n")
                self._send_json(500, {"error": msg})
            except Exception as e:
                sys.stderr.write(f"acknowledge-drift failed: {e}\n")
                self._send_json(500, {"error": str(e)})

        def do_POST(self):
            if self.path == "/api/promote":
                self._handle_promote()
            elif self.path == "/api/rescan":
                self._handle_rescan()
            elif self.path == "/api/scan-from-ticket":
                self._handle_scan_from_ticket()
            elif self.path == "/api/create-skill":
                self._handle_create_skill()
            elif self.path == "/api/promote-skill":
                self._handle_promote_skill()
            elif self.path == "/api/rescan-drift":
                self._handle_rescan_drift()
            elif self.path == "/api/acknowledge-drift":
                self._handle_acknowledge_drift()
            else:
                self.send_error(404, "not found")

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-dir", required=True)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--bind", default="127.0.0.1",
        help="Address to bind. Default 127.0.0.1 (loopback only). "
             "Use 0.0.0.0 to accept connections from your LAN, your "
             "tailnet (Tailscale), or any non-loopback interface. "
             "Be aware: 0.0.0.0 exposes the server to anyone on those "
             "networks — fine for demo/dev with fake data, think twice "
             "if the wiki carries real customer context.",
    )
    ap.add_argument("--proposals-repo", default=None,
                    help="GitHub slug for /api/promote, e.g. oscarkang24/wiki-proposals. "
                         "If omitted, /api/promote returns 503.")
    ap.add_argument("--proposals-checkout", default=str(Path.home() / ".cache" / "wiki-proposals"))
    ap.add_argument("--data-dir", default=None,
                    help="Context-center data dir (parent of wikis/, candidates/) for /api/rescan. "
                         "If omitted, /api/rescan returns 503.")
    ap.add_argument("--repo-name", default="customer-context wiki",
                    help="Pass-through to build_html_site.py during rescan rebuilds.")
    args = ap.parse_args()

    site_dir = Path(args.site_dir).resolve()
    checkout_dir = Path(args.proposals_checkout).expanduser().resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else None

    if not site_dir.is_dir():
        sys.exit(f"--site-dir does not exist: {site_dir}")
    if data_dir is not None and not data_dir.is_dir():
        sys.exit(f"--data-dir does not exist: {data_dir}")

    handler = make_handler(site_dir, args.proposals_repo, checkout_dir, data_dir, args.repo_name)

    # Set SO_REUSEADDR so a rapid restart after Ctrl-C doesn't fail to bind on
    # the lingering TIME_WAIT socket from the previous run.
    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with _Server((args.bind, args.port), handler) as httpd:
        # When binding to 0.0.0.0, log both the loopback URL (always works
        # locally) and a hint about the broader binding so users know they
        # can reach it from other devices.
        url = f"http://127.0.0.1:{args.port}/index.html"
        print(f"serving {site_dir} at {url}", file=sys.stderr)
        if args.bind != "127.0.0.1":
            print(
                f"  bind={args.bind} — also reachable from other devices on "
                f"the same network at http://<this-host>:{args.port}/",
                file=sys.stderr,
            )
        if args.proposals_repo:
            print(f"promote target: {args.proposals_repo} (checkout: {checkout_dir})", file=sys.stderr)
        else:
            print("promote: disabled (no --proposals-repo)", file=sys.stderr)
        if data_dir:
            print(f"rescan source: {data_dir}", file=sys.stderr)
        else:
            print("rescan: disabled (no --data-dir)", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
