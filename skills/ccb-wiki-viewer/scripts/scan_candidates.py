#!/usr/bin/env python3
"""Scan one or more customer wiki dirs for reusable-skill candidates.

Walks the wiki tree, sends gist files to Claude, asks it to identify
clusters of similar workflows that could be generalized into a reusable
skill, and writes one stub per cluster into the output dir.

The "rescan" button in the context-center viewer shells out to this script.

Usage:
    python3 scan_candidates.py \\
        --wikis-root=examples/sample_context_center/wikis \\
        --output-dir=examples/sample_context_center/candidates

LLM call: shells out to `claude -p "<prompt>"`. No SDK install, no API key
handling — relies on the user's existing Claude Code auth.

Output layout (under --output-dir):
    index.md                          # candidates landing page
    <cluster-id>/
        candidate.md                  # name, description, rationale, draft SKILL.md
        sources.json                  # which gist files fed this cluster
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# Files we don't want to feed to the clustering prompt: meta files (index,
# critique), giant narrative docs, and personal/team context that is
# customer-specific by definition. The cluster signal lives in the
# table-level `sources/` gists (bq_query_patterns.md, dataplex_*.md, etc.).
SKIP_NAMES = {"index.md", "CRITIQUE.md"}
SKIP_DIR_NAMES = {"personal_context"}


def collect_gist_files(wikis_root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(wikis_root.rglob("*.md")):
        if p.name in SKIP_NAMES:
            continue
        if any(part in SKIP_DIR_NAMES for part in p.relative_to(wikis_root).parts):
            continue
        out.append(p)
    return out


def build_prompt(wikis_root: Path, files: list[Path], max_chars_per_file: int) -> str:
    """Build the clustering prompt. Each file is included with its relative
    path as a header so the LLM can cite evidence by path."""
    parts = [
        "You are analyzing markdown gist files extracted from one or more",
        "customer-context wikis. Your job: identify clusters of similar",
        "workflows or query patterns that recur across the wiki(s) and could",
        "be generalized into a reusable Claude Code skill.",
        "",
        "A good candidate is:",
        "- A workflow that appears 2+ times across different tables, datasets,",
        "  or customers (the more, the higher the confidence).",
        "- General enough that it would be useful for a future customer too,",
        "  not specific to one table or one company.",
        "- Concrete enough that you can describe what the skill would *do*,",
        "  not just what topic it covers.",
        "",
        "Examples of good candidates: \"audit which dashboards still hit a",
        "deprecated table\", \"summarize per-table query patterns from",
        "INFORMATION_SCHEMA.JOBS_BY_PROJECT\", \"detect partition-filter",
        "regressions from slot-usage spikes\".",
        "",
        "Bad candidates: anything that just describes the customer's",
        "situation (\"Acme has 5 tables\"), pure facts about specific tables,",
        "or topics too vague to action (\"data governance\").",
        "",
        "Output strict JSON only, wrapped in a ```json code fence. Schema:",
        "",
        "```json",
        "{",
        '  "candidates": [',
        "    {",
        '      "id": "kebab-case-id",',
        '      "name": "Short Title Case Name",',
        '      "description": "1-2 sentences: what the skill does",',
        '      "rationale": "why this generalizes; what evidence supports it",',
        '      "confidence": "high" | "medium" | "low",',
        '      "evidence": ["relative/path/to/gist.md", ...],',
        '      "skill_md_draft": "# Name\\n\\nMarkdown skill stub: when to trigger, inputs, outputs, key steps. Keep under 300 words."',
        "    }",
        "  ]",
        "}",
        "```",
        "",
        "Aim for 2-5 candidates. Skip clusters of 1 file. Use the relative",
        f"paths shown below (anchored at `{wikis_root.name}/`) as evidence values.",
        "",
        "---",
        "",
        "## Wiki gist files",
        "",
    ]

    for p in files:
        rel = p.relative_to(wikis_root.parent).as_posix()
        text = p.read_text(encoding="utf-8")
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + f"\n\n_(truncated at {max_chars_per_file} chars)_"
        parts.append(f"### `{rel}`")
        parts.append("")
        parts.append(text)
        parts.append("")

    return "\n".join(parts)


def build_ticket_prompt(wikis_root: Path,
                        gist_files: list[Path],
                        ticket_path: Path,
                        max_chars_per_file: int) -> str:
    """Build a prompt that asks for ONE candidate skill: a culprit-finding
    workflow synthesized from a single support ticket plus the customer's
    data context (wiki gists)."""
    parts = [
        "You are turning a customer support ticket into a reusable",
        "culprit-finding skill — a parameterized debugging workflow that",
        "walks the customer's data model to diagnose this *type* of complaint.",
        "",
        "The customer's data context is the wiki gist files below. The",
        "support ticket is also below. Synthesize ONE candidate skill stub.",
        "",
        "The skill should:",
        "- Be parameterized by the ID/field types the ticket carries",
        "  (e.g. client_id, transaction_id, bug_id, dashboard_id) — these",
        "  become inputs the user supplies on each invocation.",
        "- Walk specific tables/sources from the wiki to diagnose; cite the",
        "  table or source by name in the workflow steps.",
        "- Be reusable for the *next* customer with a similar-shape",
        "  complaint, not just this one specific case.",
        "",
        "Output strict JSON only, wrapped in a ```json code fence, with",
        "EXACTLY ONE entry in the candidates array. Schema:",
        "",
        "```json",
        "{",
        '  "candidates": [',
        "    {",
        '      "id": "kebab-case-id",',
        '      "name": "Short Title Case Name",',
        '      "description": "1-2 sentences: what the skill does",',
        '      "rationale": "what about this ticket and the wiki tells you this generalizes",',
        '      "confidence": "high" | "medium" | "low",',
        '      "evidence": ["tickets/<id>/ticket.md", "wikis/<customer>/<file>", ...],',
        '      "skill_md_draft": "# Name\\n\\nMarkdown skill stub: When to trigger, Inputs (with types), Step-by-step lookup workflow citing tables, Outputs. Keep under 400 words."',
        "    }",
        "  ]",
        "}",
        "```",
        "",
        "---",
        "",
        "## Ticket",
        "",
    ]
    ticket_text = ticket_path.read_text(encoding="utf-8")
    if len(ticket_text) > max_chars_per_file * 2:
        ticket_text = ticket_text[: max_chars_per_file * 2] + "\n\n_(truncated)_"
    parts.append(f"### `{ticket_path.relative_to(ticket_path.parents[2]).as_posix()}`")
    parts.append("")
    parts.append(ticket_text)
    parts.append("")
    parts.append("## Wiki gists (data model context)")
    parts.append("")
    for p in gist_files:
        rel = p.relative_to(wikis_root.parent).as_posix()
        text = p.read_text(encoding="utf-8")
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + f"\n\n_(truncated at {max_chars_per_file} chars)_"
        parts.append(f"### `{rel}`")
        parts.append("")
        parts.append(text)
        parts.append("")
    return "\n".join(parts)


def call_claude(prompt: str, model: str | None) -> str:
    """Shell out to `claude -p`. Returns the raw stdout text.

    When the parent is itself a Claude Code session, strip CLAUDECODE plus
    the host-managed auth env vars so the nested `claude` falls back to the
    user's stored OAuth credentials instead of failing on a session-scoped
    API key. When the parent is a normal shell, leave the env alone — the
    user might be using ANTHROPIC_API_KEY for auth on purpose.
    """
    cmd = ["claude", "-p"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)

    env = dict(os.environ)
    if env.get("CLAUDECODE"):
        for k in list(env.keys()):
            if (
                k in ("CLAUDECODE", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")
                or k.startswith("CLAUDE_CODE_")
                or k.startswith("CLAUDE_AGENT_")
            ):
                env.pop(k, None)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude -p failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )
    return proc.stdout


_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Pull the first ```json ... ``` fence out of the response. Falls back to
    parsing the whole response as JSON if no fence is present."""
    m = _FENCE_RE.search(text)
    blob = m.group(1) if m else text.strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"could not parse JSON from claude response: {e}\n--- raw ---\n{text[:1000]}"
        )


def slugify(s: str, max_len: int = 60) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return (out[:max_len] or "candidate").rstrip("-")


def _write_one_candidate(c: dict, output_dir: Path) -> str:
    """Write a single candidate's subdir + sources.json. Returns the slug."""
    cid = slugify(str(c.get("id") or c.get("name") or "candidate"))
    target = output_dir / cid
    suffix = 2
    while target.exists():
        target = output_dir / f"{cid}-{suffix}"
        suffix += 1
    target.mkdir()
    cid = target.name

    confidence = str(c.get("confidence", "?")).lower()
    name = c.get("name", cid)
    description = c.get("description", "")
    rationale = c.get("rationale", "")
    evidence = c.get("evidence") or []
    origin = c.get("origin") or "scan"  # "scan" (cluster rescan) or "ticket"
    skill_md = c.get("skill_md_draft") or "_(no draft)_"

    body = [
        f"# {name}",
        "",
        f"**Confidence:** {confidence}  ·  **Origin:** {origin}",
        "",
        "## Description",
        "",
        description,
        "",
        "## Why this generalizes",
        "",
        rationale,
        "",
        "## Evidence",
        "",
    ]
    if evidence:
        for path in evidence:
            body.append(f"- `{path}`")
    else:
        body.append("_(none)_")
    body += ["", "## Draft skill", "", skill_md, ""]
    (target / "candidate.md").write_text("\n".join(body), encoding="utf-8")
    (target / "sources.json").write_text(
        json.dumps(
            {
                "id": cid,
                "name": name,
                "confidence": confidence,
                "origin": origin,
                "description": description,
                "evidence": evidence,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return cid


def _regenerate_index(output_dir: Path) -> None:
    """Rewrite output_dir/index.md from the sources.json files in each
    subdirectory. Sorts by confidence then name."""
    metas = []
    for sub in output_dir.iterdir():
        if not sub.is_dir():
            continue
        sj = sub / "sources.json"
        if not sj.exists():
            continue
        try:
            metas.append((sub.name, json.loads(sj.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            continue

    if not metas:
        (output_dir / "index.md").write_text(
            "# Candidates\n\n_No reusable patterns yet. Click Rescan, or generate "
            "one from a ticket._\n",
            encoding="utf-8",
        )
        return

    rank = {"high": 0, "medium": 1, "low": 2}
    # Sort: bridge_score desc (when present, populated by score_candidates.py),
    # then confidence asc, then name. A high-bridge candidate is one that
    # would close known gaps in the wiki — the most actionable thing the
    # user can promote next.
    has_scores = any("bridge_score" in m for _, m in metas)
    # bridge_score is a depth-weighted float (severity × coverage_fraction
    # summed across gaps). Negate for descending sort; falls back to 0 for
    # candidates that haven't been scored yet.
    metas.sort(key=lambda nm: (
        -float(nm[1].get("bridge_score") or 0.0),
        rank.get(str(nm[1].get("confidence")).lower(), 3),
        nm[1].get("name", ""),
    ))

    lines = [
        "# Candidates",
        "",
        f"_{len(metas)} candidate skill(s). Last update: "
        f"{dt.datetime.now().isoformat(timespec='seconds')}_",
        "",
    ]
    if has_scores:
        lines.append(
            "_Sorted by **bridge_score** (gap-closing value) — high-bridge "
            "candidates would close known gaps in the wiki when promoted to "
            "real skills. See `score_candidates.py` for the scoring rule._"
        )
        lines.append("")
        lines.append("| Bridge | Gaps | Confidence | Origin | Name | Description |")
        lines.append("|---:|---:|---|---|---|---|")
    else:
        lines.append("| Confidence | Origin | Name | Description |")
        lines.append("|---|---|---|---|")
    for cid, m in metas:
        confidence = str(m.get("confidence", "?")).lower()
        origin = str(m.get("origin", "scan"))
        name = m.get("name", cid)
        description = (m.get("description") or "").replace("|", "\\|").replace("\n", " ")
        if has_scores:
            score = float(m.get("bridge_score") or 0.0)
            addressed = m.get("gaps_addressed") or []
            # gaps_addressed schema is depth-weighted now: list of
            # {gap_id, severity, coverage}. Old shape was list[str] of bare
            # IDs — accept either so historical sources.json files still render.
            n_gaps = len(addressed)
            n_full = sum(
                1 for a in addressed
                if isinstance(a, dict) and a.get("coverage", 0) >= 0.99
            )
            gaps_cell = f"{n_gaps}" + (f" ({n_full} full)" if n_full else "")
            score_cell = f"**{score:.1f}**" if score > 0 else "0.0"
            lines.append(
                f"| {score_cell} | {gaps_cell} | {confidence} | {origin} | "
                f"[{name}]({cid}/candidate.md) | {description} |"
            )
        else:
            lines.append(f"| {confidence} | {origin} | [{name}]({cid}/candidate.md) | {description} |")
    (output_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_candidates(result: dict, output_dir: Path, append: bool = False,
                     default_origin: str = "scan") -> list[str]:
    """Write candidates to output_dir.

    - append=False: wipe output_dir, then write all candidates in `result`.
    - append=True: keep existing subdirs, add new candidates alongside, then
      regenerate the index.

    Returns the list of newly-written candidate slugs (in result order).
    """
    if not append and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = result.get("candidates") or []
    written = []
    for c in candidates:
        c.setdefault("origin", default_origin)
        written.append(_write_one_candidate(c, output_dir))

    _regenerate_index(output_dir)
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wikis-root", required=True,
                    help="Dir containing one or more customer wiki subdirs")
    ap.add_argument("--output-dir", required=True,
                    help="Where to write the candidates/ subtree (overwritten "
                         "in cluster mode; appended in --ticket-file mode)")
    ap.add_argument("--ticket-file", default=None,
                    help="If set: synthesize ONE candidate from this ticket file "
                         "+ wiki gists, append (don't wipe) the output dir, and "
                         "print the new candidate's slug to stdout.")
    ap.add_argument("--model", default=None, help="Pass to `claude --model`")
    ap.add_argument("--max-chars-per-file", type=int, default=4000,
                    help="Truncate each gist file at this many chars before prompting")
    ap.add_argument("--response-file", default=None,
                    help="Skip the LLM call; parse this file as the response instead "
                         "(for debugging the parser/writer in isolation)")
    args = ap.parse_args()

    wikis_root = Path(args.wikis_root).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not wikis_root.is_dir():
        sys.exit(f"--wikis-root does not exist: {wikis_root}")

    files = collect_gist_files(wikis_root)
    if not files:
        sys.exit(f"no gist .md files found under {wikis_root}")

    if args.ticket_file:
        ticket_path = Path(args.ticket_file).resolve()
        if not ticket_path.is_file():
            sys.exit(f"--ticket-file does not exist: {ticket_path}")
        print(f"==> Synthesizing candidate from ticket {ticket_path.name} + "
              f"{len(files)} wiki gists", file=sys.stderr)
        prompt = build_ticket_prompt(wikis_root, files, ticket_path, args.max_chars_per_file)
        default_origin = "ticket"
        append = True
    else:
        print(f"==> Scanning {len(files)} gist files under {wikis_root}", file=sys.stderr)
        prompt = build_prompt(wikis_root, files, args.max_chars_per_file)
        default_origin = "scan"
        append = False

    print(f"==> Prompt size: {len(prompt):,} chars", file=sys.stderr)
    if args.response_file:
        print(f"==> Reading canned response from {args.response_file}", file=sys.stderr)
        raw = Path(args.response_file).read_text(encoding="utf-8")
    else:
        print("==> Calling claude -p (this may take 10-60s)", file=sys.stderr)
        raw = call_claude(prompt, args.model)
    result = extract_json(raw)

    new_slugs = write_candidates(result, output_dir, append=append, default_origin=default_origin)
    print(f"==> Wrote {len(new_slugs)} candidate(s) to {output_dir}", file=sys.stderr)
    # Print new slugs (one per line) on stdout so the caller can locate them.
    for s in new_slugs:
        print(s)


if __name__ == "__main__":
    main()
