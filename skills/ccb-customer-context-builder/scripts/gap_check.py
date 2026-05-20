#!/usr/bin/env python3
"""Detect structural and coverage gaps in one customer wiki.

Three latent graphs, two diffs:

  1. SOURCE GRAPH       — entities × source files (what the sources actually
                          cover). Built from sources/*.md by entity extraction.
  2. WIKI-EXPLICIT GRAPH — narrative × source (what the wiki claims to
                          connect). Built from dep_graph.json (cited
                          relationships).
  3. WIKI-IMPLICIT GRAPH — entity × entity (what the wiki implies). Built
                          from co-occurrence in narrative files.

Diffs:
  - implicit ∖ explicit  → structural gaps. Two entities co-occur in
                           narrative paragraphs but are never explicitly
                           cited together. "You wrote about both, didn't link them."
  - source ∖ explicit    → coverage gaps. An entity appears in source gists
                           but the narrative doesn't cite it anywhere.
                           "The source has it, your wiki doesn't."

Outputs `GAPS.md` (human-readable) + `GAPS.json` (machine-readable, for the
side panel) at the wiki root.

Entity extraction: uses spaCy's en_core_web_sm if available; falls back to
regex over BQ table-style identifiers and source slug names. Add custom
patterns via --custom-pattern (regex, repeatable).

Usage:
    python3 gap_check.py --wiki-root=path/to/customer
    python3 gap_check.py --wiki-root=path/to/customer --top-n=20
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------- networkx (optional, for cluster-mode) ----------------

_NX = None
_NX_LOAD_ERROR: str | None = None


def _load_networkx():
    global _NX, _NX_LOAD_ERROR
    if _NX is not None or _NX_LOAD_ERROR is not None:
        return _NX
    try:
        import networkx as _nx_mod  # noqa: F401
        _NX = _nx_mod
    except ImportError:
        _NX_LOAD_ERROR = (
            "networkx not installed (pip install networkx) — falling back to "
            "pair-based gap detection only. Install for cluster-based gaps "
            "(Louvain communities + betweenness centrality, InfraNodus-style)."
        )
    return _NX


# ---------------- spaCy (optional) ----------------

_SPACY_NLP = None
_SPACY_LOAD_ERROR: str | None = None


def _load_spacy():
    global _SPACY_NLP, _SPACY_LOAD_ERROR
    if _SPACY_NLP is not None or _SPACY_LOAD_ERROR is not None:
        return _SPACY_NLP
    try:
        import spacy  # noqa: F401
        try:
            _SPACY_NLP = spacy.load("en_core_web_sm")
        except OSError as e:
            _SPACY_LOAD_ERROR = (
                f"spaCy is installed but the 'en_core_web_sm' model isn't "
                f"downloaded. Run: python -m spacy download en_core_web_sm "
                f"({e})"
            )
    except ImportError:
        _SPACY_LOAD_ERROR = "spaCy not installed (pip install spacy)."
    return _SPACY_NLP


# ---------------- Entity extraction ----------------

# BigQuery table identifiers in `dataset.table` or `project.dataset.table` form.
# Lowercase + underscores only — rejects CamelCase code identifiers like
# `entrySource.description`. The leading lowercase + ≥1 underscore in the
# table segment further reduces false positives from prose.
BQ_TABLE_RE = re.compile(
    r"\b[a-z][a-z0-9_]{2,}\.[a-z][a-z0-9_]+_[a-z0-9_]+(?:\.[a-z][a-z0-9_]+)?\b"
)

# Bare table-like names with underscores (fact_*, dim_*, *_summary, *_v2, etc.).
TABLE_NAME_RE = re.compile(
    r"\b(?:fact|dim|stg|raw|events|orders)_[a-z][a-z0-9_]{2,}\b"
    r"|\b[a-z][a-z0-9_]+_(?:summary|daily|raw|v\d+)\b"
)

# Owner-style emails as entities (people are part of the context graph).
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

# Email domains we never treat as entities. Service-account principals
# (gserviceaccount.com, iam.gserviceaccount.com) co-occur with everything
# in BQ jobs/query-pattern gists, generating noisy "structural gaps"
# between every pair of service accounts the wiki touches. They're not
# meaningful concepts — they're identity for the *retrieval*, not for
# the customer's data model. Same goes for the local OS user's gcloud
# email when the warehouse agent ran under it.
EMAIL_DOMAIN_BLOCKLIST = (
    "gserviceaccount.com",
    "iam.gserviceaccount.com",
)


def _is_blocked_email(email: str) -> bool:
    domain = email.split("@", 1)[1] if "@" in email else ""
    return any(domain.endswith(b) for b in EMAIL_DOMAIN_BLOCKLIST)

# Suffixes we never want to treat as entities — filenames and common
# generic words. Matches against the full normalized entity string.
ENTITY_BLOCKLIST_SUFFIX = (".md", ".json", ".html", ".py", ".sql", ".txt", ".yaml", ".yml")
# fields.md / lineage.md / index.md are covered by ENTITY_BLOCKLIST_SUFFIX
# above; keep the bare-name forms (fields / lineage / summary / overview)
# since those collide with prose words and are NOT caught by the suffix.
ENTITY_BLOCKLIST = {
    "none", "null", "true", "false", "data", "table", "schema",
    "fields", "lineage",
    "summary", "overview",
}


def _allowed_entity(s: str) -> bool:
    if s in ENTITY_BLOCKLIST:
        return False
    if any(s.endswith(suf) for suf in ENTITY_BLOCKLIST_SUFFIX):
        return False
    return True


@dataclass
class EntitySet:
    """Container for entities found in a piece of text."""
    tables: set[str] = field(default_factory=set)
    emails: set[str] = field(default_factory=set)
    spacy_orgs: set[str] = field(default_factory=set)
    spacy_products: set[str] = field(default_factory=set)
    custom: set[str] = field(default_factory=set)

    def all(self) -> set[str]:
        return self.tables | self.emails | self.spacy_orgs | self.spacy_products | self.custom


def normalize(s: str) -> str:
    return s.strip().lower()


def _add(target: set[str], raw: str) -> None:
    s = normalize(raw)
    if _allowed_entity(s):
        target.add(s)


def extract_entities(text: str, custom_patterns: list[re.Pattern]) -> EntitySet:
    es = EntitySet()
    for m in BQ_TABLE_RE.finditer(text):
        _add(es.tables, m.group(0))
    for m in TABLE_NAME_RE.finditer(text):
        _add(es.tables, m.group(0))
    for m in EMAIL_RE.finditer(text):
        e = normalize(m.group(0))
        if not _is_blocked_email(e):
            _add(es.emails, m.group(0))
    for pat in custom_patterns:
        for m in pat.finditer(text):
            _add(es.custom, m.group(0))

    nlp = _load_spacy()
    if nlp is not None:
        # Cap text length for spaCy — large docs slow it down a lot.
        doc = nlp(text[:200_000])
        for ent in doc.ents:
            if ent.label_ == "ORG":
                _add(es.spacy_orgs, ent.text)
            elif ent.label_ == "PRODUCT":
                _add(es.spacy_products, ent.text)
    return es


# ---------------- File discovery ----------------

SKIP_FILE_NAMES = ("CRITIQUE.md", "GAPS.md", "DRIFT.md")


def is_source_file(rel: Path) -> bool:
    return any(part == "sources" for part in rel.parts[:-1])


def is_index_file(rel: Path) -> bool:
    return rel.name == "index.md"


def collect_files(wiki_root: Path) -> tuple[list[Path], list[Path]]:
    """Return (narrative_files, source_files), both wiki-rooted absolutes.

    Excludes auto-generated nav inside sources/ (sources/index.md, sources/
    nested index files) — they're navigation, not source content."""
    narrative: list[Path] = []
    source: list[Path] = []
    for p in sorted(wiki_root.rglob("*.md")):
        rel = p.relative_to(wiki_root)
        if rel.name in SKIP_FILE_NAMES:
            continue
        if is_source_file(rel):
            # Skip the auto-generated index inside sources/.
            if rel.name == "index.md":
                continue
            source.append(p)
        else:
            narrative.append(p)
    return narrative, source


# ---------------- Graphs ----------------

@dataclass
class Graphs:
    # entity -> set of source files containing it
    source_to_entities: dict[str, set[str]] = field(default_factory=dict)
    entity_to_sources: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # entity co-occurrence within narrative paragraphs
    entity_pair_cooccurrence: Counter = field(default_factory=Counter)
    # which narrative files mention which entity
    entity_to_narratives: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # explicit citations (from dep_graph.json): narrative -> set of source files
    narrative_cites_source: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def build_source_graph(
    source_files: list[Path], wiki_root: Path,
    custom_patterns: list[re.Pattern],
) -> Graphs:
    g = Graphs()
    for sf in source_files:
        rel = sf.relative_to(wiki_root).as_posix()
        text = sf.read_text(encoding="utf-8", errors="replace")
        ents = extract_entities(text, custom_patterns).all()
        g.source_to_entities[rel] = ents
        for e in ents:
            g.entity_to_sources[e].add(rel)
    return g


def build_implicit_graph(
    narrative_files: list[Path], wiki_root: Path, g: Graphs,
    custom_patterns: list[re.Pattern],
) -> None:
    """Co-occurrence within paragraphs of narrative files."""
    for nf in narrative_files:
        rel = nf.relative_to(wiki_root).as_posix()
        text = nf.read_text(encoding="utf-8", errors="replace")
        # Strip claim footnote definitions so they don't pollute co-occurrence.
        text_no_footnotes = re.sub(
            r"^\s*\[\^c\d+\]:.*$", "", text, flags=re.MULTILINE,
        )
        # Split into paragraphs (blank-line separated).
        for para in re.split(r"\n\s*\n", text_no_footnotes):
            if not para.strip():
                continue
            ents = extract_entities(para, custom_patterns).all()
            for e in ents:
                g.entity_to_narratives[e].add(rel)
            # Pairs co-occurring in the same paragraph.
            ents_sorted = sorted(ents)
            for a, b in itertools.combinations(ents_sorted, 2):
                g.entity_pair_cooccurrence[(a, b)] += 1


def build_explicit_graph(wiki_root: Path, g: Graphs) -> None:
    """Read dep_graph.json (which encodes citations) and populate
    narrative_cites_source. If dep_graph.json is missing, compute
    nothing — coverage gaps will still work, structural gaps degrade
    gracefully (everything looks structural)."""
    dep_path = wiki_root / "dep_graph.json"
    if not dep_path.is_file():
        return
    try:
        dep = json.loads(dep_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    for edge in dep.get("edges", []):
        g.narrative_cites_source[edge["from"]].add(edge["to"])


# ---------------- Gap detection ----------------

@dataclass
class Gap:
    id: str
    type: str            # "structural" | "coverage"
    severity: str        # "high" | "medium" | "low"
    concepts: list[str]
    pages: list[str]     # narrative pages where the gap manifests
    sources: list[str]   # underlying source files (for context)
    evidence: str
    suggested_bridge: str
    auto_fixable: bool


def make_gap_id(kind: str, key: str) -> str:
    """Build a stable gap id from a kind tag and an arbitrary key string.

    Python's built-in ``hash()`` is salted per-process (PYTHONHASHSEED),
    so the same pair would otherwise get a different gap-id every run —
    breaking the wiki-viewer's "Promote bridge" buttons across rebuilds.
    sha256 is deterministic across runs. Mirrors ``make_drift_id`` in
    ``source_diff.py``.
    """
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    return f"gap-{kind}-{h}"


def detect_structural_gaps(g: Graphs, top_n: int) -> list[Gap]:
    """Pairs of entities that co-occur in narrative paragraphs but are
    never explicitly cited together (i.e. the narrative pages mentioning
    them don't both cite a common source pair)."""
    gaps: list[Gap] = []
    # Score = co-occurrence count × min(narrative-prevalence of each entity).
    # Narrative-prevalence: how many narrative files mention this entity.
    # Pairs where both entities are widely mentioned but never bridged are
    # the InfraNodus-style "structural gap" signal.
    scored: list[tuple[float, tuple[str, str], int]] = []
    for (a, b), cooc in g.entity_pair_cooccurrence.items():
        # Skip pairs where one is a substring of the other (e.g. owner email
        # vs. their domain) — these are noise.
        if a in b or b in a:
            continue
        prev_a = len(g.entity_to_narratives.get(a, set()))
        prev_b = len(g.entity_to_narratives.get(b, set()))
        if prev_a == 0 or prev_b == 0:
            continue
        # Are they ever "explicitly bridged"? An explicit bridge = a single
        # narrative file cites a source containing entity A AND a source
        # containing entity B. (Loose by design: we want the recall to be
        # generous so the Gaps panel surfaces candidate bridges; the
        # bridge_score signal in score_candidates.py is the precision filter.)
        bridged = False
        sources_with_a = g.entity_to_sources.get(a, set())
        sources_with_b = g.entity_to_sources.get(b, set())
        for narrative, cites in g.narrative_cites_source.items():
            if cites & sources_with_a and cites & sources_with_b:
                bridged = True
                break
        if bridged:
            continue
        score = cooc * min(prev_a, prev_b)
        scored.append((score, (a, b), cooc))

    scored.sort(reverse=True)
    for score, (a, b), cooc in scored[:top_n]:
        # Severity: by score percentile within this run.
        if score >= 4:
            severity = "high"
        elif score >= 2:
            severity = "medium"
        else:
            severity = "low"
        pages = sorted(
            g.entity_to_narratives.get(a, set())
            & g.entity_to_narratives.get(b, set())
        )
        sources = sorted(
            g.entity_to_sources.get(a, set())
            | g.entity_to_sources.get(b, set())
        )
        gid = make_gap_id("S", f"{a}|{b}")
        gaps.append(Gap(
            id=gid, type="structural", severity=severity,
            concepts=[a, b], pages=pages, sources=sources,
            evidence=f"co-occurs in {cooc} paragraph(s) across {len(pages)} narrative file(s); "
                     f"never explicitly cited together",
            suggested_bridge=(
                f"Add a citation in one of {pages[:2]} that bridges "
                f"`{a}` and `{b}` via {sources[:1]}."
                if pages and sources else
                f"Cite a source that mentions both `{a}` and `{b}`."
            ),
            auto_fixable=False,  # auto-fix needs an LLM in the loop; defer
        ))
    return gaps


def detect_cluster_gaps(
    g: Graphs, top_n: int,
    *, density_thresholds: tuple[float, float, float] = (0.05, 0.15, 0.25),
) -> list[Gap]:
    """InfraNodus-style cluster-pair structural gaps.

    Builds a co-occurrence graph from `entity_pair_cooccurrence`, runs
    Louvain community detection to find topical clusters, computes
    betweenness centrality for each node, and surfaces pairs of clusters
    that are both important (high cumulative centrality) but poorly
    bridged (low cross-cluster edge density).

    Pair-based detect_structural_gaps stays the primary signal; cluster
    gaps are an additional, coarser-grained lens. Returns [] if networkx
    isn't installed.
    """
    nx = _load_networkx()
    if nx is None or not g.entity_pair_cooccurrence:
        return []
    from networkx.algorithms.community import louvain_communities

    G = nx.Graph()
    for (a, b), w in g.entity_pair_cooccurrence.items():
        if a == b:
            continue
        G.add_edge(a, b, weight=int(w))
    if G.number_of_nodes() < 4 or G.number_of_edges() < 3:
        return []  # too small to cluster meaningfully

    # Louvain — non-deterministic; pin seed for reproducibility.
    try:
        communities = louvain_communities(G, weight="weight", seed=42)
    except Exception as e:
        # Older networkx versions don't accept `seed` — retry without it.
        try:
            communities = louvain_communities(G, weight="weight")
        except Exception:
            return []
    # Drop trivially-small communities (a single node isn't a cluster).
    communities = [c for c in communities if len(c) >= 2]
    if len(communities) < 2:
        return []

    centrality = nx.betweenness_centrality(G, weight="weight", normalized=True)

    # For every pair of communities, compute importance + density.
    results: list[tuple[float, float, set[str], set[str], int, int]] = []
    for i in range(len(communities)):
        for j in range(i + 1, len(communities)):
            ci, cj = communities[i], communities[j]
            cross = 0
            for u in ci:
                for v in cj:
                    if G.has_edge(u, v):
                        cross += 1
            potential = len(ci) * len(cj)
            density = cross / potential if potential else 0.0
            importance = sum(centrality.get(n, 0.0) for n in ci | cj)
            results.append((importance, density, ci, cj, cross, potential))

    # Severity rule:
    #   density < 0.05 AND importance in top 25% of pairs → high
    #   density < 0.15 AND importance in top 50%          → medium
    #   anything else (within pair-list) flagged          → low
    if not results:
        return []
    importances = sorted((r[0] for r in results), reverse=True)
    if not importances:
        return []
    p75_imp = importances[max(0, len(importances) // 4)]
    p50_imp = importances[len(importances) // 2]

    high_max, med_max, low_max = density_thresholds
    # density >= the LOW threshold means the clusters are well-enough bridged
    # not to flag at all; a small headroom above low_max is treated as
    # "well-bridged" and skipped.
    well_bridged = max(low_max + 0.05, 0.30)

    gaps: list[Gap] = []
    for importance, density, ci, cj, cross, potential in results:
        if density >= well_bridged:
            continue  # well-bridged, not a gap
        if importance < importances[-1] + 1e-9:
            continue
        if density < high_max and importance >= p75_imp:
            sev = "high"
        elif density < med_max and importance >= p50_imp:
            sev = "medium"
        elif density < low_max:
            sev = "low"
        else:
            continue

        # Pick representative concepts: top 3 by centrality from each cluster.
        def top_concepts(cluster: set[str], k: int = 3) -> list[str]:
            return sorted(cluster, key=lambda n: -centrality.get(n, 0.0))[:k]
        rep_a = top_concepts(ci)
        rep_b = top_concepts(cj)

        ci_key = ",".join(sorted(ci))
        cj_key = ",".join(sorted(cj))
        gid = make_gap_id("CL", f"{ci_key}|{cj_key}")
        narratives_a = set().union(*(g.entity_to_narratives.get(n, set()) for n in ci))
        narratives_b = set().union(*(g.entity_to_narratives.get(n, set()) for n in cj))
        pages = sorted(narratives_a | narratives_b)
        sources_a = set().union(*(g.entity_to_sources.get(n, set()) for n in ci))
        sources_b = set().union(*(g.entity_to_sources.get(n, set()) for n in cj))
        all_sources = sorted(sources_a | sources_b)

        gaps.append(Gap(
            id=gid, type="cluster_structural", severity=sev,
            concepts=rep_a + ["↔"] + rep_b,
            pages=pages, sources=all_sources,
            evidence=(
                f"Cluster A ({len(ci)} concepts incl. {', '.join(f'`{c}`' for c in rep_a)}) "
                f"and Cluster B ({len(cj)} concepts incl. {', '.join(f'`{c}`' for c in rep_b)}) "
                f"have only {cross}/{potential} cross-cluster edges "
                f"(density={density:.2f}, importance={importance:.3f}) — "
                f"poorly bridged but both topically important"
            ),
            suggested_bridge=(
                f"Add a citation that connects something from Cluster A "
                f"(e.g. `{rep_a[0]}`) with something from Cluster B "
                f"(e.g. `{rep_b[0]}`) via a source that mentions both."
            ),
            auto_fixable=False,
        ))

    # Sort by severity then importance.
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (sev_rank.get(g.severity, 9), g.id))
    return gaps[:top_n]


def detect_coverage_gaps(g: Graphs, top_n: int) -> list[Gap]:
    """Entities that appear in source files but are never mentioned in any
    narrative file."""
    gaps: list[Gap] = []
    for entity, sources in g.entity_to_sources.items():
        if entity in g.entity_to_narratives:
            continue  # mentioned somewhere in narrative
        # Skip noise: very short tokens, well-known generic words.
        if len(entity) < 4:
            continue
        if entity in {"none", "null", "true", "false", "data", "table", "schema"}:
            continue
        score = len(sources)
        if score >= 3:
            severity = "high"
        elif score == 2:
            severity = "medium"
        else:
            severity = "low"
        gid = make_gap_id("C", entity)
        gaps.append(Gap(
            id=gid, type="coverage", severity=severity,
            concepts=[entity], pages=[], sources=sorted(sources),
            evidence=f"appears in {len(sources)} source file(s) but no narrative file mentions it",
            suggested_bridge=(
                f"Add a paragraph (likely in `data_warehouse.md` or the "
                f"appropriate `{{table}}/lineage.md`) covering `{entity}`, "
                f"with a citation to one of: {sorted(sources)[:2]}."
            ),
            auto_fixable=False,
        ))
    gaps.sort(key=lambda g: (-len(g.sources), g.concepts[0]))
    return gaps[:top_n]


# ---------------- Output ----------------

def severity_emoji(sev: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")


def render_md(gaps: list[Gap], wiki_root: Path) -> str:
    n_struct = sum(1 for g in gaps if g.type == "structural")
    n_cover = sum(1 for g in gaps if g.type == "coverage")
    n_cluster = sum(1 for g in gaps if g.type == "cluster_structural")
    summary = f"**{n_struct}** structural · **{n_cover}** coverage"
    if n_cluster:
        summary += f" · **{n_cluster}** cluster"
    lines: list[str] = [
        f"# Gaps — {wiki_root.name}",
        "",
        f"_Generated by `gap_check.py` at {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}._",
        "",
        summary,
        "",
    ]
    by_type: dict[str, list[Gap]] = defaultdict(list)
    for g in gaps:
        by_type[g.type].append(g)
    for typ, label in (
        ("structural", "Structural gaps"),
        ("coverage", "Coverage gaps"),
        ("cluster_structural", "Cluster gaps (Louvain communities + betweenness)"),
    ):
        if not by_type.get(typ):
            continue
        lines.append(f"## {label}")
        lines.append("")
        if typ == "structural":
            lines.append(
                "_Two concepts both appear in your narrative but the wiki never "
                "explicitly bridges them — likely missed citations._"
            )
        elif typ == "coverage":
            lines.append(
                "_Concepts present in source gists but not mentioned in any narrative "
                "file — sections you didn't write up._"
            )
        else:  # cluster_structural
            lines.append(
                "_Pairs of concept clusters that are both topically important "
                "(high cumulative betweenness) but poorly bridged across the "
                "wiki — InfraNodus-style structural gaps at the cluster level._"
            )
        lines.append("")
        for g in by_type[typ]:
            concept_label = " ↔ ".join(f"`{c}`" for c in g.concepts) \
                if typ == "structural" else f"`{g.concepts[0]}`"
            lines.append(f"### {g.id} — {concept_label}")
            lines.append("")
            lines.append(f"- **Severity:** {g.severity} {severity_emoji(g.severity)}")
            lines.append(f"- **Evidence:** {g.evidence}")
            if g.pages:
                lines.append(f"- **Affected narrative pages:** {', '.join(f'`{p}`' for p in g.pages[:5])}"
                             + (f" (+{len(g.pages)-5} more)" if len(g.pages) > 5 else ""))
            if g.sources:
                lines.append(f"- **Source files:** {', '.join(f'`{s}`' for s in g.sources[:5])}"
                             + (f" (+{len(g.sources)-5} more)" if len(g.sources) > 5 else ""))
            lines.append(f"- **Suggested bridge:** {g.suggested_bridge}")
            lines.append("")
    if not gaps:
        lines.append("_No gaps detected._")
        lines.append("")
    return "\n".join(lines)


def render_json(gaps: list[Gap], wiki_root: Path) -> dict:
    return {
        "schema": "gaps.v1",
        "wiki_root": wiki_root.name,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spacy_used": _SPACY_NLP is not None,
        "spacy_status": _SPACY_LOAD_ERROR or "loaded" if _SPACY_NLP else _SPACY_LOAD_ERROR,
        "gap_count": len(gaps),
        "by_type": {
            "structural": sum(1 for g in gaps if g.type == "structural"),
            "coverage": sum(1 for g in gaps if g.type == "coverage"),
            "cluster_structural": sum(1 for g in gaps if g.type == "cluster_structural"),
        },
        "by_severity": {
            sev: sum(1 for g in gaps if g.severity == sev)
            for sev in ("high", "medium", "low")
        },
        "gaps": [asdict(g) for g in gaps],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki-root", required=True)
    ap.add_argument("--top-n", type=int, default=15,
                    help="Max gaps per type to surface (default 15).")
    ap.add_argument(
        "--cluster-mode", action="store_true",
        help="Also run InfraNodus-style cluster gap detection: Louvain "
             "community detection on the entity co-occurrence graph + "
             "betweenness centrality, surface cluster pairs with high "
             "importance and low cross-cluster edge density. Requires "
             "networkx (pip install networkx). Adds cluster_structural "
             "gaps on top of the pair-based structural and coverage gaps.",
    )
    ap.add_argument(
        "--cluster-thresholds", default="0.05,0.15,0.25",
        help="Comma-separated cross-cluster edge density thresholds for "
             "high,medium,low severity. Default: 0.05,0.15,0.25 (a cluster "
             "pair with density < 5%% is HIGH if importance is also in the "
             "top 25%% of pairs in this run, etc.). Loosen these (e.g. "
             "0.10,0.25,0.40) to surface more cluster gaps on a small wiki; "
             "tighten them on a wiki where clusters are tightly bridged.",
    )
    ap.add_argument("--custom-pattern", action="append", default=[],
                    help="Extra entity regex (repeatable). Compiled with re.IGNORECASE.")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        sys.exit(f"--wiki-root not a directory: {wiki_root}")

    custom_patterns = [
        re.compile(p, re.IGNORECASE) for p in args.custom_pattern
    ]

    narrative_files, source_files = collect_files(wiki_root)
    if not args.quiet:
        nlp = _load_spacy()
        if nlp is None:
            print(f"note: {_SPACY_LOAD_ERROR} (regex-only entity extraction)",
                  file=sys.stderr)

    g = build_source_graph(source_files, wiki_root, custom_patterns)
    build_implicit_graph(narrative_files, wiki_root, g, custom_patterns)
    build_explicit_graph(wiki_root, g)

    structural = detect_structural_gaps(g, args.top_n)
    coverage = detect_coverage_gaps(g, args.top_n)
    cluster: list[Gap] = []
    if args.cluster_mode:
        if _load_networkx() is None and not args.quiet:
            print(f"note: {_NX_LOAD_ERROR}", file=sys.stderr)
        try:
            thresh_vals = tuple(float(x) for x in args.cluster_thresholds.split(","))
            if len(thresh_vals) != 3:
                raise ValueError(f"expected 3 values, got {len(thresh_vals)}")
            for v in thresh_vals:
                if not (0.0 <= v <= 1.0):
                    raise ValueError(f"value out of [0,1]: {v}")
        except ValueError as e:
            sys.exit(f"--cluster-thresholds must be 3 comma-separated floats in [0,1]: {e}")
        cluster = detect_cluster_gaps(g, args.top_n, density_thresholds=thresh_vals)
    gaps = structural + coverage + cluster

    md_path = wiki_root / "GAPS.md"
    json_path = wiki_root / "GAPS.json"
    md_path.write_text(render_md(gaps, wiki_root), encoding="utf-8")
    json_path.write_text(
        json.dumps(render_json(gaps, wiki_root), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not args.quiet:
        print(
            f"gaps: {len(structural)} structural · {len(coverage)} coverage "
            f"→ {md_path.name}, {json_path.name}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
