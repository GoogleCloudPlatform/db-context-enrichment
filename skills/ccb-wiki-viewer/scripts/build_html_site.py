#!/usr/bin/env python3
"""Build a portable static-HTML viewer for a generated customer-context wiki.

Two modes:

(1) Single-section mode (back-compat with original wiki-viewer):
    --input-dir points at a single wiki tree. Output mirrors the .md tree
    one-to-one as .html under --output-dir. No top tabs.

(2) Context-center mode (new):
    --input-dir contains any subset of these subdirs:
        wikis/         (per-customer wikis)
        tickets/       (incoming support tickets)
        candidates/    (auto-detected reusable patterns)
        skills/        (promoted reusable skills)
        drift/         (source-of-truth drift reports)
    Each detected subdir becomes a top tab (5 max, in the order above —
    see SECTIONS below). Each tab is rendered into output_dir/<section>/.
    The top-level output_dir/index.html redirects to the first available
    section. Section indexes are auto-generated if missing.

Per-page features (both modes):
- Each *.md becomes a *.html in the same relative location.
- Sidebar with the section's tree (current file highlighted).
- Content rendered via marked.js (CDN).
- Intra-wiki *.md links rewritten to *.html.
- Edit/Promote selection toolbar (posts to /api/promote when served via
  promote_server.py; inert on the static server).
- Rescan button on the Candidates tab landing page (posts to /api/rescan).

Usage:
    # Single-section
    python3 scripts/build_html_site.py \\
        --input-dir=customer-context/context \\
        --output-dir=customer-context/site

    # Context-center
    python3 scripts/build_html_site.py \\
        --input-dir=examples/sample_context_center \\
        --output-dir=examples/sample_context_center_site
"""
from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import socketserver
import sys
import webbrowser
from pathlib import Path


# Recognized section names and their display labels (in tab order).
# Order encodes the demo flow: data context (wikis) → user signals (tickets)
# → detected workflows (candidates) → reusable artifacts (skills).
SECTIONS = [
    ("wikis", "Wikis"),
    ("tickets", "Tickets"),
    ("candidates", "Candidates"),
    ("skills", "Skills"),
    ("drift", "Drift"),
]


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; color: #1f2328; display: flex; flex-direction: column; }}

  /* Top tabs (only present in context-center mode) */
  #tabs {{
    display: flex; align-items: stretch;
    background: #1f2328; color: #f6f8fa;
    border-bottom: 1px solid #d1d9e0; flex-shrink: 0;
  }}
  #tabs .brand {{
    padding: 12px 18px; font-weight: 600; font-size: 13px;
    letter-spacing: 0.04em; text-transform: uppercase;
    border-right: 1px solid #2d333b; color: #f6f8fa;
  }}
  #tabs .tab {{
    padding: 12px 20px; font-size: 13.5px; color: #adbac7;
    text-decoration: none; border-right: 1px solid #2d333b;
    display: inline-flex; align-items: center; gap: 6px;
  }}
  #tabs .tab:hover {{ color: #f6f8fa; background: #2d333b; }}
  #tabs .tab.active {{ color: white; background: #0969da; font-weight: 600; }}
  #tabs .tab .count {{
    font-size: 11px; background: rgba(255,255,255,0.18);
    padding: 1px 7px; border-radius: 9px;
  }}

  #layout {{ display: flex; flex: 1; min-height: 0; }}
  #sidebar {{
    width: 340px; overflow-y: auto;
    background: #f6f8fa; border-right: 1px solid #d1d9e0;
    padding: 18px 14px; flex-shrink: 0;
  }}
  #sidebar header {{ margin-bottom: 12px; }}
  #sidebar h1 {{ font-size: 13px; margin: 0; text-transform: uppercase; letter-spacing: 0.05em; color: #57606a; }}
  #sidebar h1 a {{ color: inherit; text-decoration: none; }}
  #sidebar .root-meta {{ font-size: 11px; color: #6e7781; margin-top: 2px; }}
  #sidebar ul {{ list-style: none; padding-left: 14px; margin: 2px 0; }}
  #sidebar > ul {{ padding-left: 0; }}
  #sidebar li {{ font-size: 12.5px; line-height: 1.55; }}
  #sidebar a {{ color: #0969da; text-decoration: none; }}
  #sidebar a:hover {{ text-decoration: underline; }}
  #sidebar a.current {{
    font-weight: 600; color: #1a7f37; background: #dafbe1;
    padding: 1px 5px; border-radius: 3px;
  }}
  #sidebar .dir {{ color: #57606a; font-weight: 600; margin-top: 4px; cursor: default; }}
  #sidebar .file-icon, #sidebar .dir-icon {{ display: inline-block; width: 14px; opacity: 0.6; margin-right: 2px; font-size: 10px; }}
  #content {{ flex: 1; overflow-y: auto; padding: 28px 44px; }}

  /* Gaps side panel (Wikis tab only, when GAPS.json present).
     In-flow flex column on wide viewports; collapses to position:fixed
     bottom drawer on narrow viewports so it never gets pushed off-screen. */
  #gaps-panel {{
    width: 340px; flex-shrink: 0;
    overflow-y: auto;
    background: #fff4d6;
    border-left: 3px solid #d4a72c;
    padding: 18px 16px;
    font-size: 13px;
  }}
  #gaps-panel h2 {{
    font-size: 13px; margin: 0 0 6px;
    text-transform: uppercase; letter-spacing: 0.06em; color: #1f2328;
    font-weight: 700;
  }}
  /* Narrow viewport: drop the panel below the content instead of letting
     flex squeeze the main column or push the panel off-screen. */
  @media (max-width: 1100px) {{
    #layout {{ flex-direction: column; }}
    #sidebar {{ width: 100%; height: auto; max-height: 220px; }}
    #gaps-panel {{
      width: 100%;
      max-height: 320px;
      border-left: none;
      border-top: 3px solid #d4a72c;
    }}
  }}
  #gaps-panel .gp-header-counts {{
    font-size: 11px; color: #6e7781; margin-bottom: 14px;
  }}
  #gaps-panel .gp-empty {{
    color: #6e7781; font-style: italic; padding: 6px 0;
  }}
  #gaps-panel .gap {{
    background: white; border: 1px solid #e6e8eb; border-left-width: 4px;
    border-radius: 5px; padding: 10px 12px; margin-bottom: 10px;
  }}
  #gaps-panel .gap.sev-high {{ border-left-color: #cf222e; }}
  #gaps-panel .gap.sev-medium {{ border-left-color: #d4a72c; }}
  #gaps-panel .gap.sev-low {{ border-left-color: #1a7f37; }}
  #gaps-panel .gap-meta {{
    display: flex; gap: 6px; align-items: center;
    font-size: 10.5px; color: #57606a;
    text-transform: uppercase; letter-spacing: 0.04em;
    margin-bottom: 4px;
  }}
  #gaps-panel .gap-sev-badge {{
    display: inline-block; padding: 1px 6px; border-radius: 8px;
    font-weight: 600; color: white; letter-spacing: 0.03em;
  }}
  #gaps-panel .gap-sev-badge.sev-high {{ background: #cf222e; }}
  #gaps-panel .gap-sev-badge.sev-medium {{ background: #bf8700; }}
  #gaps-panel .gap-sev-badge.sev-low {{ background: #1a7f37; }}
  #gaps-panel .gap-id {{ font-family: ui-monospace, monospace; }}
  #gaps-panel .gap-wiki-tag {{
    margin-left: auto; padding: 1px 6px; border-radius: 3px;
    background: #ddf4ff; color: #0860c8;
    font-size: 9.5px; font-weight: 600; letter-spacing: 0.04em;
    text-transform: lowercase;
  }}
  #gaps-panel .gap-concepts {{
    font-size: 13.5px; font-weight: 600; line-height: 1.4;
    margin: 4px 0; word-wrap: break-word;
  }}
  #gaps-panel .gap-concepts code {{
    background: #f0f3f6; padding: 1px 4px; border-radius: 3px;
    font-size: 12.5px;
  }}
  #gaps-panel .gap-evidence {{
    font-size: 12px; color: #1f2328; line-height: 1.45; margin-bottom: 6px;
  }}
  #gaps-panel .gap-bridge {{
    font-size: 12px; color: #1f2328; line-height: 1.45;
    background: #f0f6fc; border-left: 2px solid #54aeff;
    padding: 6px 8px; margin-top: 6px;
  }}
  #gaps-panel .gap-bridge strong {{ color: #0860c8; }}
  #gaps-panel .gap-actions {{
    margin-top: 8px; display: flex; gap: 6px;
  }}
  #gaps-panel .gap-actions button {{
    border: 1px solid #d1d9e0; background: white;
    color: #1f2328; padding: 4px 9px;
    font: 600 11.5px/1 -apple-system, system-ui, sans-serif;
    border-radius: 4px; cursor: pointer;
  }}
  #gaps-panel .gap-actions button:hover {{ background: #f6f8fa; }}
  #gaps-panel .gap-actions .promote-bridge {{
    background: #1f883d; color: white; border-color: #1f883d;
  }}
  #gaps-panel .gap-actions .promote-bridge:hover {{ background: #1a7f37; }}
  #gaps-panel .gap-all-link {{
    display: block; text-align: center; font-size: 12px;
    margin-top: 12px; color: #0969da; text-decoration: none;
    padding: 6px; border: 1px dashed #d1d9e0; border-radius: 4px;
  }}
  #gaps-panel .gap-all-link:hover {{ background: white; border-style: solid; }}

  #breadcrumb {{ font-size: 12.5px; color: #57606a; margin-bottom: 18px; padding-bottom: 10px; border-bottom: 1px solid #d1d9e0; }}
  #breadcrumb a {{ color: #0969da; text-decoration: none; }}
  #breadcrumb a:hover {{ text-decoration: underline; }}
  #breadcrumb .sep {{ margin: 0 6px; color: #afb8c1; }}
  .markdown-body {{ max-width: 920px; }}
  .markdown-body h1:first-child {{ margin-top: 0; }}
  .file-meta {{ font-size: 12px; color: #6e7781; margin-bottom: 16px; }}
  .file-meta code {{ background: #eaeef2; padding: 1px 4px; border-radius: 3px; }}

  /* Claim citation footnotes (gap_check.py / claims_sidecar.py) */
  .markdown-body sup.cite {{
    font-size: 9.5px; font-weight: 700; padding: 1px 5px;
    margin-left: 2px; border-radius: 8px;
    color: white; vertical-align: super; line-height: 1;
    cursor: pointer; text-decoration: none;
  }}
  .markdown-body sup.cite a {{ color: inherit; text-decoration: none; }}
  .markdown-body sup.cite.cite-extracted {{ background: #1f883d; }}
  .markdown-body sup.cite.cite-inferred  {{ background: #0969da; }}
  .markdown-body sup.cite.cite-ambiguous {{ background: #bf8700; }}
  .markdown-body sup.cite.cite-unknown   {{ background: #6e7781; }}
  .markdown-body sup.cite:hover {{ filter: brightness(1.15); }}

  .markdown-body .citations-block {{
    margin-top: 32px; padding-top: 16px; border-top: 1px solid #d1d9e0;
    font-size: 12.5px;
  }}
  .markdown-body .citations-block h2 {{
    font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;
    color: #57606a; margin: 0 0 10px;
  }}
  .markdown-body .citation-row {{
    display: flex; gap: 8px; padding: 4px 0;
    line-height: 1.5;
  }}
  .markdown-body .citation-row .cite-id {{
    font-family: ui-monospace, monospace;
    color: #57606a; min-width: 28px; font-weight: 600;
  }}
  .markdown-body .citation-row .cite-tag {{
    display: inline-block; padding: 1px 6px; border-radius: 3px;
    font-size: 10px; font-weight: 700; color: white;
    text-transform: uppercase; letter-spacing: 0.04em;
    height: 16px; line-height: 14px; margin-top: 2px;
    flex-shrink: 0;
  }}
  .markdown-body .citation-row .cite-tag.cite-extracted {{ background: #1f883d; }}
  .markdown-body .citation-row .cite-tag.cite-inferred  {{ background: #0969da; }}
  .markdown-body .citation-row .cite-tag.cite-ambiguous {{ background: #bf8700; }}
  .markdown-body .citation-row .cite-body {{ flex: 1; word-break: break-word; }}
  .markdown-body .citation-row .cite-body code {{
    font-size: 11.5px; background: #f0f3f6; padding: 1px 4px; border-radius: 3px;
  }}
  .markdown-body .citation-row a.cite-back {{
    color: #6e7781; text-decoration: none; font-size: 13px;
  }}
  .markdown-body .citation-row a.cite-back:hover {{ color: #0969da; }}
  .markdown-body sup.cite.fn-current {{
    outline: 2px solid #fb8500; outline-offset: 1px;
  }}
  .markdown-body .citation-row.fn-current {{
    background: #fff8c5; padding: 4px 6px; border-radius: 4px;
  }}

  /* Action bars (Candidates tab) */
  .action-bar {{
    border-radius: 6px; padding: 10px 14px; margin-bottom: 18px;
    display: flex; align-items: center; gap: 12px;
  }}
  .action-bar .label {{ font-size: 13px; color: #57606a; flex: 1; }}
  .action-bar code {{ background: rgba(0,0,0,0.05); padding: 1px 4px; border-radius: 3px; }}
  #rescan-bar {{ background: #fff8c5; border: 1px solid #d4a72c; }}
  #create-skill-bar {{ background: #ddf4ff; border: 1px solid #54aeff; }}
  #promote-skill-bar {{ background: #dafbe1; border: 1px solid #4ac26b; }}
  #from-ticket-bar  {{ background: #fbefff; border: 1px solid #c297ff; }}
  .action-bar button {{
    color: white; border: none;
    padding: 7px 14px; border-radius: 6px; cursor: pointer;
    font: 600 13px/1 -apple-system, system-ui, sans-serif;
  }}
  .action-bar button:disabled {{ background: #8c959f !important; cursor: wait; }}
  #rescan-btn {{ background: #1f883d; }}
  #rescan-btn:hover {{ background: #1a7f37; }}
  #create-skill-btn {{ background: #0969da; }}
  #create-skill-btn:hover {{ background: #0860c8; }}
  #promote-skill-btn {{ background: #1f883d; }}
  #promote-skill-btn:hover {{ background: #1a7f37; }}
  #from-ticket-btn   {{ background: #8250df; }}
  #from-ticket-btn:hover   {{ background: #6f42c1; }}

  /* Promote / Edit selection toolbar */
  #sel-toolbar {{
    position: absolute; z-index: 9999; display: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18); border-radius: 6px;
    overflow: hidden; user-select: none;
  }}
  #sel-toolbar button {{
    border: none; padding: 6px 12px;
    font: 600 12px/1 -apple-system, system-ui, sans-serif;
    color: white; cursor: pointer;
  }}
  #sel-toolbar button:disabled {{ background: #8c959f !important; cursor: wait; }}
  #sel-toolbar .promote-btn {{ background: #1f883d; }}
  #sel-toolbar .promote-btn:hover {{ background: #1a7f37; }}
  #sel-toolbar .edit-btn    {{ background: #0969da; border-left: 1px solid rgba(255,255,255,0.25); }}
  #sel-toolbar .edit-btn:hover {{ background: #0860c8; }}

  /* Edit modal */
  #edit-backdrop {{
    position: fixed; inset: 0; z-index: 10000;
    background: rgba(15,20,25,0.45); display: none;
    align-items: center; justify-content: center;
  }}
  #edit-modal {{
    background: white; width: min(680px, 92vw); max-height: 80vh;
    display: flex; flex-direction: column;
    border-radius: 8px; box-shadow: 0 12px 36px rgba(0,0,0,0.3);
    padding: 18px 20px;
  }}
  #edit-modal h2 {{ margin: 0 0 8px; font-size: 14px; color: #57606a; text-transform: uppercase; letter-spacing: 0.05em; }}
  #edit-modal .original-preview {{
    font-size: 12.5px; color: #57606a; background: #f6f8fa;
    border-left: 3px solid #d1d9e0; padding: 8px 10px;
    margin-bottom: 12px; max-height: 120px; overflow-y: auto;
    white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, monospace;
  }}
  #edit-modal label {{ font-size: 12px; color: #57606a; font-weight: 600; margin-bottom: 4px; }}
  #edit-modal textarea {{
    width: 100%; min-height: 160px; flex: 1;
    padding: 10px 12px; font: 13px/1.5 ui-monospace, monospace;
    border: 1px solid #d1d9e0; border-radius: 6px; resize: vertical;
    box-sizing: border-box;
  }}
  #edit-modal textarea:focus {{ outline: none; border-color: #0969da; box-shadow: 0 0 0 3px rgba(9,105,218,0.18); }}
  #edit-modal .actions {{ margin-top: 12px; display: flex; gap: 8px; justify-content: flex-end; }}
  #edit-modal button {{
    padding: 7px 14px; font: 600 13px/1 -apple-system, system-ui, sans-serif;
    border-radius: 6px; cursor: pointer; border: 1px solid transparent;
  }}
  #edit-modal .btn-cancel {{ background: white; color: #1f2328; border-color: #d1d9e0; }}
  #edit-modal .btn-cancel:hover {{ background: #f6f8fa; }}
  #edit-modal .btn-submit {{ background: #0969da; color: white; }}
  #edit-modal .btn-submit:hover {{ background: #0860c8; }}
  #edit-modal .btn-submit:disabled {{ background: #8c959f; cursor: wait; }}

  #promote-toast {{
    position: fixed; bottom: 24px; right: 24px; z-index: 10001;
    background: #1f2328; color: white; padding: 12px 16px;
    border-radius: 6px; font-size: 13px; max-width: 420px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25); display: none;
  }}
  #promote-toast.error {{ background: #cf222e; }}
  #promote-toast a {{ color: #79c0ff; }}
</style>
</head>
<body>
{tabs_html}
<div id="layout">
<nav id="sidebar">
  <header>
    <h1><a href="{root_index_href}">{repo_name}</a></h1>
    <div class="root-meta">{tree_meta}</div>
  </header>
  {sidebar_html}
</nav>
<main id="content">
  <div id="breadcrumb">{breadcrumb_html}</div>
  {action_bar_html}
  <div class="file-meta">Source: <code>{source_path}</code></div>
  <article class="markdown-body" id="rendered"></article>
</main>
{gaps_panel_html}
</div>
<pre id="md-source" style="display:none">{escaped_md}</pre>
<pre id="gaps-data" style="display:none">{gaps_data_json}</pre>
<div id="sel-toolbar">
  <button class="promote-btn" type="button">Promote</button>
  <button class="edit-btn" type="button">Edit</button>
</div>
<div id="edit-backdrop">
  <div id="edit-modal" role="dialog" aria-labelledby="edit-modal-title">
    <h2 id="edit-modal-title">Propose an edit</h2>
    <div class="original-preview" id="edit-original-preview"></div>
    <label for="edit-textarea">Proposed replacement</label>
    <textarea id="edit-textarea" spellcheck="true"></textarea>
    <div class="actions">
      <button class="btn-cancel" type="button" id="edit-cancel">Cancel</button>
      <button class="btn-submit" type="button" id="edit-submit">Submit edit</button>
    </div>
  </div>
</div>
<div id="promote-toast"></div>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<script>
  const md = document.getElementById('md-source').textContent;
  marked.setOptions({{ gfm: true, breaks: false }});

  // ---- Claim citation pre-processor ----
  // Pull [^cN]: definitions out of the body so marked doesn't render them
  // inline; replace [^cN] references with anchored, color-coded superscripts;
  // append a tidy "Citations" block at the end with each definition's tag,
  // source pointer, and (for EXTRACTED) verbatim quote.
  function preprocessCitations(srcMd) {{
    const defRe = /^\\s*\\[\\^(c\\d+)\\]:\\s*(.+?)\\s*$/gm;
    const defs = {{}};
    const order = [];
    let mNoDefs = srcMd.replace(defRe, (m, id, body) => {{
      if (!(id in defs)) order.push(id);
      defs[id] = body;
      return '';
    }});
    // Parse each def into {{tag, sources, quote, raw}} via the same shape
    // claims_sidecar.py uses (· separated; first field is tag).
    function parseDef(body) {{
      const parts = body.split('·').map(s => s.trim());
      const tag = (parts[0] || '').toUpperCase();
      const sources = [];
      let quote = null;
      if (parts.length >= 2) {{
        const sb = parts[1];
        const re = /`([^`]+)`/g;
        let mm;
        while ((mm = re.exec(sb)) !== null) sources.push(mm[1]);
      }}
      if (tag === 'EXTRACTED' && parts.length >= 3) {{
        const qb = parts.slice(2).join(' · ');
        const qm = qb.match(/"([^"]*)"\\s*$/);
        if (qm) quote = qm[1];
      }}
      return {{ tag, sources, quote, raw: body }};
    }}
    const parsed = {{}};
    for (const id of order) parsed[id] = parseDef(defs[id]);

    const tagClass = (t) => {{
      const v = (t || '').toLowerCase();
      if (v === 'extracted' || v === 'inferred' || v === 'ambiguous') return 'cite-' + v;
      return 'cite-unknown';
    }};

    // Replace [^cN] in body with superscript anchored to the citation block.
    const refRe = /\\[\\^(c\\d+)\\]/g;
    const seen = new Set();
    const mBody = mNoDefs.replace(refRe, (m, id) => {{
      const p = parsed[id];
      if (!p) return m;  // orphan — leave literal so the issue is visible
      seen.add(id);
      const cls = tagClass(p.tag);
      const num = id.slice(1);
      const titleAttr = (p.tag || '?') + (p.sources.length ? ' · ' + p.sources.join(', ') : '');
      return `<sup class="cite ${{cls}}" id="ref-${{id}}"><a href="#fn-${{id}}" title="${{titleAttr.replace(/"/g, '&quot;')}}">${{num}}</a></sup>`;
    }});

    // Render the citations block. Markdown for the source pointer prose +
    // verbatim quote so marked still styles the inline `code` and italics.
    let block = '';
    if (order.length) {{
      const parts = ['', '', '<div class="citations-block">', '<h2>Citations</h2>'];
      for (const id of order) {{
        const p = parsed[id];
        const cls = tagClass(p.tag);
        const num = id.slice(1);
        let body = p.raw
          .replace(/^[A-Z_]+\\s*·\\s*/, '')  // strip leading TAG ·
          .trim();
        // Render backticked source pointers as inline code spans.
        body = body.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Italicize the quoted verbatim string.
        body = body.replace(/"([^"]*)"/g, '<em>"$1"</em>');
        // Escape the rest minimally — we just inserted <code> and <em>
        // ourselves, the rest of the body is plain prose we trust.
        const back = seen.has(id)
          ? `<a href="#ref-${{id}}" class="cite-back" title="back to citation">↩</a>`
          : '';
        parts.push(
          `<div class="citation-row" id="fn-${{id}}">` +
          `<span class="cite-id">${{num}}.</span>` +
          `<span class="cite-tag ${{cls}}">${{(p.tag || '?').toLowerCase()}}</span>` +
          `<span class="cite-body">${{body}} ${{back}}</span>` +
          `</div>`
        );
      }}
      parts.push('</div>');
      block = parts.join('\\n');
    }}
    return mBody + block;
  }}

  document.getElementById('rendered').innerHTML = marked.parse(preprocessCitations(md));

  // Click a superscript or back-arrow → highlight both ends briefly.
  function flashLink(elFn, refFn) {{
    document.querySelectorAll('.fn-current').forEach(n => n.classList.remove('fn-current'));
    const a = elFn();
    const b = refFn();
    if (a) a.classList.add('fn-current');
    if (b) b.classList.add('fn-current');
    setTimeout(() => {{
      if (a) a.classList.remove('fn-current');
      if (b) b.classList.remove('fn-current');
    }}, 2000);
  }}
  document.querySelectorAll('.markdown-body sup.cite a').forEach(a => {{
    a.addEventListener('click', () => {{
      const id = a.parentNode.id.replace(/^ref-/, '');
      flashLink(() => a.parentNode, () => document.getElementById('fn-' + id));
    }});
  }});
  document.querySelectorAll('.markdown-body a.cite-back').forEach(a => {{
    a.addEventListener('click', () => {{
      const targetId = (a.getAttribute('href') || '').replace(/^#ref-/, '');
      flashLink(
        () => document.getElementById('fn-' + targetId),
        () => document.getElementById('ref-' + targetId),
      );
    }});
  }});

  // Rewrite intra-wiki .md links to .html so navigation works
  document.querySelectorAll('#rendered a').forEach(a => {{
    const href = a.getAttribute('href');
    if (!href) return;
    if (/^https?:\\/\\//i.test(href) || href.startsWith('#')) return;
    if (href.endsWith('.md')) {{
      a.setAttribute('href', href.replace(/\\.md(#|$)/, '.html$1'));
    }} else if (href.includes('.md#')) {{
      a.setAttribute('href', href.replace(/\\.md#/, '.html#'));
    }}
  }});

  // ---- Render gaps side panel (Wikis tab only) ----
  (function renderGapsPanel() {{
    const panel = document.getElementById('gaps-panel');
    if (!panel) return;
    const dataNode = document.getElementById('gaps-data');
    if (!dataNode) {{ panel.style.display = 'none'; return; }}
    let gaps;
    try {{ gaps = JSON.parse(dataNode.textContent || '[]'); }}
    catch (e) {{ gaps = []; }}
    const list = panel.querySelector('.gp-list');
    if (!gaps.length) {{
      list.innerHTML = '<div class="gp-empty">No gaps detected for this page.</div>';
      return;
    }}
    const sevRank = {{ high: 0, medium: 1, low: 2 }};
    gaps.sort((a, b) => (sevRank[a.severity] ?? 3) - (sevRank[b.severity] ?? 3));
    const esc = (s) => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const renderConcepts = (g) => g.concepts.map(c => `<code>${{esc(c)}}</code>`).join(
      g.type === 'structural' ? ' &harr; ' : ''
    );
    list.innerHTML = gaps.map(g => {{
      const wikiTag = g._wiki_label
        ? `<span class="gap-wiki-tag">${{esc(g._wiki_label)}}</span>`
        : '';
      return `
      <div class="gap sev-${{esc(g.severity)}}">
        <div class="gap-meta">
          <span class="gap-sev-badge sev-${{esc(g.severity)}}">${{esc(g.severity)}}</span>
          <span>${{esc(g.type)}}</span>
          <span class="gap-id">${{esc(g.id)}}</span>
          ${{wikiTag}}
        </div>
        <div class="gap-concepts">${{renderConcepts(g)}}</div>
        <div class="gap-evidence">${{esc(g.evidence)}}</div>
        <div class="gap-bridge"><strong>Suggested bridge:</strong> ${{esc(g.suggested_bridge)}}</div>
        <div class="gap-actions">
          <button type="button" class="promote-bridge" data-gap-id="${{esc(g.id)}}">Promote bridge</button>
        </div>
      </div>
      `;
    }}).join('');
    // Hook up promote-bridge buttons. They post the gap as a "promote" payload
    // so the existing /api/promote endpoint opens a PR with the suggestion.
    list.querySelectorAll('.promote-bridge').forEach(btn => {{
      btn.addEventListener('click', async () => {{
        const gapId = btn.dataset.gapId;
        const g = gaps.find(x => x.id === gapId);
        if (!g) return;
        const restore = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Promoting...';
        const selection =
          `Gap ${{g.id}} (${{g.type}}, ${{g.severity}}): ${{g.concepts.join(' ↔ ')}}\\n\\n` +
          `${{g.evidence}}\\n\\nSuggested bridge: ${{g.suggested_bridge}}`;
        try {{
          const r = await fetch('/api/promote', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              kind: 'promote',
              selection,
              source_path: SOURCE_PATH,
              page_title: PAGE_TITLE + ' — gap ' + g.id,
              surrounding_context: 'auto-generated by gap_check.py',
              page_url: window.location.href,
            }}),
          }});
          const data = await r.json().catch(() => ({{}}));
          if (!r.ok) {{
            showToast('Promote bridge failed: ' + (data.error || r.statusText), true);
          }} else {{
            showToast('PR opened: <a href="' + data.pr_url + '" target="_blank" rel="noopener">' + data.pr_url + '</a>');
          }}
        }} catch (err) {{
          showToast('Promote bridge failed: ' + err.message, true);
        }} finally {{
          btn.disabled = false;
          btn.textContent = restore;
        }}
      }});
    }});
  }})();

  // ---- Promote / Edit on selection ----
  const SOURCE_PATH = {source_path_json};   // section-relative (e.g. TICKET-.../ticket.md)
  const DATA_PATH   = {data_path_json};     // data-dir relative (e.g. tickets/TICKET-.../ticket.md) — what the API endpoints expect
  const PAGE_TITLE  = {page_title_json};
  const rendered  = document.getElementById('rendered');
  const toolbar   = document.getElementById('sel-toolbar');
  const promoteBtn = toolbar.querySelector('.promote-btn');
  const editBtn   = toolbar.querySelector('.edit-btn');
  const toast     = document.getElementById('promote-toast');
  const backdrop  = document.getElementById('edit-backdrop');
  const editModal = document.getElementById('edit-modal');
  const editPreview = document.getElementById('edit-original-preview');
  const editTextarea = document.getElementById('edit-textarea');
  const editCancel = document.getElementById('edit-cancel');
  const editSubmit = document.getElementById('edit-submit');

  // Last selection captured at click-time, so opening the modal (which
  // takes focus and clears the selection) doesn't lose it.
  let pendingSelection = null;

  function showToast(msg, isError) {{
    toast.innerHTML = msg;
    toast.classList.toggle('error', !!isError);
    toast.style.display = 'block';
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {{ toast.style.display = 'none'; }}, 8000);
  }}

  function selectionWithinRendered() {{
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null;
    const text = sel.toString().trim();
    if (text.length < 3) return null;
    const range = sel.getRangeAt(0);
    if (!rendered.contains(range.commonAncestorContainer)) return null;
    return {{ text, range }};
  }}

  function surroundingContext(range) {{
    let node = range.commonAncestorContainer;
    if (node.nodeType === Node.TEXT_NODE) node = node.parentNode;
    const blockTags = new Set(['P','LI','TD','TH','BLOCKQUOTE','H1','H2','H3','H4','H5','H6','PRE']);
    while (node && node !== rendered && !blockTags.has(node.tagName)) {{
      node = node.parentNode;
    }}
    if (!node || node === rendered) return '';
    return (node.innerText || node.textContent || '').trim();
  }}

  function captureSelection() {{
    const info = selectionWithinRendered();
    if (!info) return null;
    return {{
      text: info.text,
      context: surroundingContext(info.range),
    }};
  }}

  function hideToolbar() {{ toolbar.style.display = 'none'; }}

  document.addEventListener('selectionchange', () => {{
    const info = selectionWithinRendered();
    if (!info) {{ hideToolbar(); return; }}
    const rect = info.range.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {{ hideToolbar(); return; }}
    toolbar.style.top  = (window.scrollY + rect.bottom + 6) + 'px';
    toolbar.style.left = (window.scrollX + rect.left) + 'px';
    toolbar.style.display = 'inline-flex';
  }});

  document.addEventListener('mousedown', (e) => {{
    if (toolbar.contains(e.target)) return;
    setTimeout(() => {{ if (!selectionWithinRendered()) hideToolbar(); }}, 0);
  }});

  async function postProposal(payload, btn, busyLabel) {{
    const restore = btn.textContent;
    btn.disabled = true;
    btn.textContent = busyLabel;
    try {{
      const r = await fetch('/api/promote', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload),
      }});
      const data = await r.json().catch(() => ({{}}));
      if (!r.ok) {{
        showToast('Failed: ' + (data.error || r.statusText), true);
        return false;
      }} else {{
        showToast('PR opened: <a href="' + data.pr_url + '" target="_blank" rel="noopener">' + data.pr_url + '</a>');
        return true;
      }}
    }} catch (err) {{
      showToast('Failed: ' + err.message, true);
      return false;
    }} finally {{
      btn.disabled = false;
      btn.textContent = restore;
    }}
  }}

  promoteBtn.addEventListener('click', async (e) => {{
    e.preventDefault();
    const sel = captureSelection();
    if (!sel) return;
    const ok = await postProposal({{
      kind: 'promote',
      selection: sel.text,
      source_path: SOURCE_PATH,
      page_title: PAGE_TITLE,
      surrounding_context: sel.context,
      page_url: window.location.href,
    }}, promoteBtn, 'Promoting...');
    if (ok) {{
      hideToolbar();
      window.getSelection().removeAllRanges();
    }}
  }});

  function openEditModal() {{
    const sel = captureSelection();
    if (!sel) return;
    pendingSelection = sel;
    editPreview.textContent = sel.text;
    editTextarea.value = sel.text;
    backdrop.style.display = 'flex';
    setTimeout(() => {{ editTextarea.focus(); editTextarea.select(); }}, 0);
  }}

  function closeEditModal() {{
    backdrop.style.display = 'none';
    pendingSelection = null;
    hideToolbar();
    window.getSelection().removeAllRanges();
  }}

  editBtn.addEventListener('click', (e) => {{ e.preventDefault(); openEditModal(); }});
  editCancel.addEventListener('click', (e) => {{ e.preventDefault(); closeEditModal(); }});
  backdrop.addEventListener('click', (e) => {{ if (e.target === backdrop) closeEditModal(); }});
  document.addEventListener('keydown', (e) => {{
    if (backdrop.style.display === 'flex' && e.key === 'Escape') closeEditModal();
  }});

  editSubmit.addEventListener('click', async (e) => {{
    e.preventDefault();
    if (!pendingSelection) return;
    const proposed = editTextarea.value.trim();
    if (!proposed) {{ showToast('Proposed text is empty.', true); return; }}
    if (proposed === pendingSelection.text.trim()) {{
      showToast('Proposed text is identical to original.', true);
      return;
    }}
    const ok = await postProposal({{
      kind: 'edit',
      original: pendingSelection.text,
      proposed: proposed,
      source_path: SOURCE_PATH,
      page_title: PAGE_TITLE,
      surrounding_context: pendingSelection.context,
      page_url: window.location.href,
    }}, editSubmit, 'Submitting...');
    if (ok) closeEditModal();
  }});

  // ---- Rescan (Candidates tab landing page only) ----
  const rescanBtn = document.getElementById('rescan-btn');
  if (rescanBtn) {{
    rescanBtn.addEventListener('click', async () => {{
      const restore = rescanBtn.textContent;
      rescanBtn.disabled = true;
      rescanBtn.textContent = 'Scanning... (10-60s)';
      try {{
        const r = await fetch('/api/rescan', {{ method: 'POST' }});
        const data = await r.json().catch(() => ({{}}));
        if (!r.ok) {{
          showToast('Rescan failed: ' + (data.error || r.statusText), true);
        }} else {{
          showToast('Rescan complete: ' + (data.candidate_count || 0) + ' candidate(s). Reloading...');
          setTimeout(() => location.reload(), 600);
        }}
      }} catch (err) {{
        showToast('Rescan failed: ' + err.message, true);
      }} finally {{
        rescanBtn.disabled = false;
        rescanBtn.textContent = restore;
      }}
    }});
  }}

  // ---- Generate culprit-finding skill from ticket (Tickets tab) ----
  const fromTicketBtn = document.getElementById('from-ticket-btn');
  if (fromTicketBtn) {{
    fromTicketBtn.addEventListener('click', async () => {{
      const restore = fromTicketBtn.textContent;
      fromTicketBtn.disabled = true;
      fromTicketBtn.textContent = 'Generating... (10-60s)';
      try {{
        const r = await fetch('/api/scan-from-ticket', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ ticket_path: DATA_PATH }}),
        }});
        const data = await r.json().catch(() => ({{}}));
        if (!r.ok) {{
          showToast('Generate failed: ' + (data.error || r.statusText), true);
        }} else {{
          const note = data.used_canned ? ' (demo mode: canned response — live claude -p auth failed)' : '';
          showToast('Candidate generated' + note + '. Opening...');
          setTimeout(() => {{ location.href = data.candidate_url || '../../candidates/index.html'; }}, 900);
        }}
      }} catch (err) {{
        showToast('Generate failed: ' + err.message, true);
      }} finally {{
        fromTicketBtn.disabled = false;
        fromTicketBtn.textContent = restore;
      }}
    }});
  }}

  // ---- Promote skill (Skills tab, SKILL.md pages only) ----
  const promoteSkillBtn = document.getElementById('promote-skill-btn');
  if (promoteSkillBtn) {{
    promoteSkillBtn.addEventListener('click', async () => {{
      const restore = promoteSkillBtn.textContent;
      promoteSkillBtn.disabled = true;
      promoteSkillBtn.textContent = 'Promoting...';
      // DATA_PATH looks like "skills/<slug>/SKILL.md" — strip filename to get the dir.
      const skillDir = DATA_PATH.replace(/\\/SKILL\\.md$/, '');
      try {{
        const r = await fetch('/api/promote-skill', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ skill_path: skillDir }}),
        }});
        const data = await r.json().catch(() => ({{}}));
        if (!r.ok) {{
          showToast('Promote skill failed: ' + (data.error || r.statusText), true);
        }} else {{
          showToast('PR opened: <a href="' + data.pr_url + '" target="_blank" rel="noopener">' + data.pr_url + '</a>');
        }}
      }} catch (err) {{
        showToast('Promote skill failed: ' + err.message, true);
      }} finally {{
        promoteSkillBtn.disabled = false;
        promoteSkillBtn.textContent = restore;
      }}
    }});
  }}

  // ---- Drift tab: Re-scan + per-entry Ack ----
  const rescanDriftBtn = document.getElementById('rescan-drift-btn');
  if (rescanDriftBtn) {{
    rescanDriftBtn.addEventListener('click', async () => {{
      const restore = rescanDriftBtn.textContent;
      rescanDriftBtn.disabled = true;
      rescanDriftBtn.textContent = 'Re-scanning...';
      try {{
        // Customer slug = the directory under drift/. DATA_PATH looks like
        // "drift/<customer>/DRIFT.md".
        const m = DATA_PATH.match(/^drift\\/([^/]+)\\//);
        const customer = m ? m[1] : '';
        const r = await fetch('/api/rescan-drift', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ customer }}),
        }});
        const data = await r.json().catch(() => ({{}}));
        if (!r.ok) {{
          showToast('Re-scan failed: ' + (data.error || r.statusText), true);
        }} else {{
          showToast('Re-scan complete: ' + (data.summary || 'done') + '. Reloading...');
          setTimeout(() => location.reload(), 600);
        }}
      }} catch (err) {{
        showToast('Re-scan failed: ' + err.message, true);
      }} finally {{
        rescanDriftBtn.disabled = false;
        rescanDriftBtn.textContent = restore;
      }}
    }});

    // Inject an "Ack" button next to every <h3> that starts with "drift-".
    // Marked renders these from "### drift-X-..." headers in DRIFT.md.
    document.querySelectorAll('#rendered h3').forEach(h => {{
      const m = (h.textContent || '').match(/^(drift-[A-Z]-[0-9a-f]+)\\b/);
      if (!m) return;
      const driftId = m[1];
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'drift-ack-btn';
      btn.textContent = 'Ack';
      btn.style.cssText =
        'margin-left: 12px; padding: 2px 10px; font: 600 11.5px/1 -apple-system, system-ui, sans-serif;' +
        ' background: white; border: 1px solid #d1d9e0; border-radius: 4px; color: #1f2328; cursor: pointer;' +
        ' vertical-align: middle;';
      btn.addEventListener('mouseenter', () => {{ btn.style.background = '#f6f8fa'; }});
      btn.addEventListener('mouseleave', () => {{ btn.style.background = 'white'; }});
      btn.addEventListener('click', async () => {{
        btn.disabled = true;
        btn.textContent = 'Acking...';
        try {{
          const m2 = DATA_PATH.match(/^drift\\/([^/]+)\\//);
          const customer = m2 ? m2[1] : '';
          const r = await fetch('/api/acknowledge-drift', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ customer, drift_id: driftId }}),
          }});
          const data = await r.json().catch(() => ({{}}));
          if (!r.ok) {{
            showToast('Ack failed: ' + (data.error || r.statusText), true);
            btn.disabled = false; btn.textContent = 'Ack';
            return;
          }}
          // Visually mark the entry as acked.
          const article = h.closest('article');
          h.style.textDecoration = 'line-through';
          h.style.color = '#8c959f';
          btn.textContent = 'Acked';
          btn.style.background = '#dafbe1';
          btn.style.borderColor = '#1a7f37';
          btn.style.color = '#1a7f37';
          showToast('Acknowledged ' + driftId + '. Will be hidden on next re-scan.');
        }} catch (err) {{
          showToast('Ack failed: ' + err.message, true);
          btn.disabled = false; btn.textContent = 'Ack';
        }}
      }});
      h.appendChild(btn);
    }});
  }}

  // ---- Create skill (Candidate detail pages only) ----
  const createSkillBtn = document.getElementById('create-skill-btn');
  if (createSkillBtn) {{
    createSkillBtn.addEventListener('click', async () => {{
      const restore = createSkillBtn.textContent;
      createSkillBtn.disabled = true;
      createSkillBtn.textContent = 'Creating skill... (1-3 min)';
      try {{
        const r = await fetch('/api/create-skill', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ candidate_path: DATA_PATH }}),
        }});
        const data = await r.json().catch(() => ({{}}));
        if (!r.ok) {{
          showToast('Create skill failed: ' + (data.error || r.statusText), true);
        }} else {{
          const where = data.skill_path || 'skills/';
          showToast('Skill created at <code>' + where + '</code>. Switching to Skills tab...');
          setTimeout(() => {{
            // Navigate to the new skill's index, fall back to skills landing.
            const target = data.skill_url || '../../skills/index.html';
            location.href = target;
          }}, 800);
        }}
      }} catch (err) {{
        showToast('Create skill failed: ' + err.message, true);
      }} finally {{
        createSkillBtn.disabled = false;
        createSkillBtn.textContent = restore;
      }}
    }});
  }}
</script>
</body>
</html>
"""


def collect_md_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def extract_h1(md_content: str, fallback: str) -> str:
    m = _H1_RE.search(md_content)
    return m.group(1).strip() if m else fallback


def render_sidebar(root: Path, output_dir: Path, current_rel: Path | None, current_html_dir: Path) -> str:
    """Recursively render the tree as nested <ul>, highlighting current_rel.

    Hrefs point into output_dir (where the .html files live), not root
    (where the .md files live). current_rel may be None for synthetic pages
    (e.g. the top-level redirect page) where nothing should be highlighted.
    """
    def render_dir(d: Path, depth: int = 0) -> list[str]:
        out = ["<ul>"] if depth == 0 else []
        children = sorted(d.iterdir(), key=lambda p: (p.is_file(), 0 if p.name == "index.md" else 1, p.name.lower()))
        files = [c for c in children if c.is_file() and c.suffix == ".md"]
        subdirs = [c for c in children if c.is_dir()]
        if depth > 0:
            out.append("<ul>")
        for f in files:
            rel = f.relative_to(root)
            html_rel = rel.with_suffix(".html")
            href = os.path.relpath(output_dir / html_rel, start=current_html_dir).replace(os.sep, "/")
            cur = ' class="current"' if rel == current_rel else ""
            label = html.escape(f.name)
            out.append(f'<li><span class="file-icon">·</span><a href="{href}"{cur}>{label}</a></li>')
        for sd in subdirs:
            out.append(f'<li class="dir"><span class="dir-icon">▾</span>{html.escape(sd.name)}/')
            out.extend(render_dir(sd, depth + 1))
            out.append("</li>")
        if depth > 0:
            out.append("</ul>")
        if depth == 0:
            out.append("</ul>")
        return out

    return "".join(render_dir(root))


def render_breadcrumb(rel_path: Path, root: Path, output_dir: Path, current_html_dir: Path) -> str:
    parts = list(rel_path.parts)
    crumbs = []
    # Root link points into output_dir, not into the input markdown tree.
    root_href = os.path.relpath(output_dir / "index.html", start=current_html_dir).replace(os.sep, "/")
    crumbs.append(f'<a href="{root_href}">{html.escape(root.name)}</a>')
    # Each intermediate dir links to its index.html if one exists.
    md_acc = root
    html_acc = output_dir
    for i, part in enumerate(parts):
        md_acc = md_acc / part
        html_acc = html_acc / part
        is_last = i == len(parts) - 1
        if is_last:
            crumbs.append(f"<strong>{html.escape(part)}</strong>")
        else:
            # Link iff the source directory has an index.md.
            if (md_acc / "index.md").exists():
                href = os.path.relpath(html_acc / "index.html", start=current_html_dir).replace(os.sep, "/")
                crumbs.append(f'<a href="{href}">{html.escape(part)}</a>')
            else:
                crumbs.append(html.escape(part))
    return '<span class="sep">›</span>'.join(crumbs)


def render_tabs(active_section: str | None,
                sections_present: list[tuple[str, str]],
                section_counts: dict[str, int],
                output_root: Path,
                current_html_dir: Path) -> str:
    """Render the top tab nav. Returns empty string in single-section mode
    (sections_present empty)."""
    if not sections_present:
        return ""
    parts = ['<nav id="tabs">']
    parts.append('<span class="brand">Context Center</span>')
    for slug, label in sections_present:
        href = os.path.relpath(
            output_root / slug / "index.html", start=current_html_dir
        ).replace(os.sep, "/")
        cls = "tab active" if slug == active_section else "tab"
        count = section_counts.get(slug, 0)
        count_html = f' <span class="count">{count}</span>' if count else ""
        parts.append(f'<a class="{cls}" href="{href}">{html.escape(label)}{count_html}</a>')
    parts.append("</nav>")
    return "".join(parts)


def render_action_bar(active_section: str | None, rel_path: Path | None) -> str:
    """Show a section-specific action bar:
    - Rescan button on candidates/index.html
    - Create-skill button on candidates/<id>/candidate.html
    - Promote-skill button on skills/<slug>/SKILL.html (always present)
    Empty string everywhere else."""
    if rel_path is None:
        return ""
    rp = rel_path.as_posix()

    if active_section == "candidates":
        if rp == "index.md":
            return (
                '<div class="action-bar" id="rescan-bar">'
                '<span class="label">Re-run pattern detection across all wikis. '
                'Calls <code>scan_candidates.py</code> via the local server.</span>'
                '<button id="rescan-btn" type="button">🔄 Rescan</button>'
                '</div>'
            )
        if rp.endswith("/candidate.md"):
            return (
                '<div class="action-bar" id="create-skill-bar">'
                '<span class="label">Promote this candidate into a real Claude Code skill via '
                '<code>/skill-creator</code>. Writes to <code>skills/&lt;slug&gt;/</code> in '
                'the data dir; rebuilds the site so the new skill shows up in the Skills tab.</span>'
                '<button id="create-skill-btn" type="button">✨ Create skill</button>'
                '</div>'
            )
        return ""

    if active_section == "tickets":
        # Show "Generate culprit-finding skill" on ticket detail pages.
        if rp.endswith("/ticket.md"):
            return (
                '<div class="action-bar" id="from-ticket-bar">'
                '<span class="label">Use this ticket + the wiki context to generate a '
                'reusable culprit-finding workflow. Lands as a candidate; promote it '
                'with <code>Create skill</code>.</span>'
                '<button id="from-ticket-btn" type="button">🔎 Generate culprit-finding skill</button>'
                '</div>'
            )
        return ""

    if active_section == "skills":
        # Show Promote on SKILL.md pages (the skill entry point).
        if rp.endswith("/SKILL.md"):
            return (
                '<div class="action-bar" id="promote-skill-bar">'
                '<span class="label">Ship this skill as a PR to your proposals repo. '
                'Requires <code>PROPOSALS_REPO</code> set when launching the server; '
                'otherwise the button shows a helpful error.</span>'
                '<button id="promote-skill-btn" type="button">🚀 Promote skill</button>'
                '</div>'
            )
        return ""

    if active_section == "drift":
        # Show Re-scan + bulk-ack on DRIFT.md detail pages.
        if rp.endswith("/DRIFT.md"):
            return (
                '<div class="action-bar" id="drift-bar">'
                '<span class="label">Re-run drift detection against the live '
                'source files for this customer (compares hashes vs. the '
                'manifest). Use the <strong>Ack</strong> button next to '
                'each entry to dismiss it from this report.</span>'
                '<button id="rescan-drift-btn" type="button">🔄 Re-scan drift</button>'
                '</div>'
            )
        return ""

    return ""


def find_wiki_root(page_abs: Path, section_root: Path) -> Path | None:
    """Walk up from page_abs until we find a directory containing GAPS.json,
    stopping at section_root. Returns None if no GAPS.json is found.

    This handles both flat layouts (wikis/<customer>/GAPS.json) and the
    bundled-demo layout (wikis/<customer>/<wiki-subdir>/GAPS.json) without
    hardcoding the depth."""
    section_root_resolved = section_root.resolve()
    cur = page_abs.resolve().parent
    while True:
        if (cur / "GAPS.json").is_file():
            return cur
        if cur == section_root_resolved or section_root_resolved not in cur.parents:
            return None
        cur = cur.parent


def gaps_for_page(
    page_abs: Path, section_root: Path, gaps_cache: dict[Path, list[dict]],
) -> list[dict]:
    """Return the subset of GAPS.json entries that reference this page.

    Filtering rule: a gap matches the current page iff the page's path
    relative to its wiki root is in `gap.pages` (structural) OR the page
    is one of the canonical "surface here" files for coverage gaps
    (index.md / data_warehouse.md), which don't have specific pages but
    deserve a hint where to add the missing concept.
    """
    wiki_root = find_wiki_root(page_abs, section_root)
    if wiki_root is None:
        return []

    if wiki_root not in gaps_cache:
        try:
            gaps_cache[wiki_root] = json.loads(
                (wiki_root / "GAPS.json").read_text(encoding="utf-8")
            ).get("gaps", [])
        except Exception:
            gaps_cache[wiki_root] = []

    all_gaps = gaps_cache[wiki_root]
    if not all_gaps:
        return []

    page_in_wiki = page_abs.resolve().relative_to(wiki_root).as_posix()
    surface_coverage_on = {"index.md", "data_warehouse.md"}

    out: list[dict] = []
    for g in all_gaps:
        if g.get("type") == "structural":
            if page_in_wiki in g.get("pages", []):
                out.append(g)
        elif g.get("type") == "coverage":
            if page_in_wiki in surface_coverage_on:
                out.append(g)
    return out


def aggregate_gaps_under(
    section_root: Path, page_dir: Path,
    gaps_cache: dict[Path, list[dict]],
    *, max_per_wiki: int = 25, top_n_total: int = 50,
) -> tuple[list[dict], int]:
    """Walk descendants of page_dir and aggregate gaps from every GAPS.json
    found. Returns (gaps, num_wikis_aggregated).

    Used on autogen landings (wikis/index.html, wikis/<customer>/index.html)
    where there's no single wiki root to scope to. Each gap is annotated
    with `_wiki_label` so the panel can show which customer it came from.

    Severity-sort and cap to top_n_total to avoid overwhelming the panel.
    """
    out: list[dict] = []
    wikis_seen = 0
    page_dir = page_dir.resolve()
    section_root = section_root.resolve()
    for gaps_path in sorted(page_dir.rglob("GAPS.json")):
        wiki_root = gaps_path.parent.resolve()
        wikis_seen += 1
        if wiki_root not in gaps_cache:
            try:
                gaps_cache[wiki_root] = json.loads(
                    gaps_path.read_text(encoding="utf-8")
                ).get("gaps", [])
            except Exception:
                gaps_cache[wiki_root] = []
        try:
            wiki_label = wiki_root.relative_to(section_root).as_posix()
        except ValueError:
            wiki_label = wiki_root.name
        for g in gaps_cache[wiki_root][:max_per_wiki]:
            annotated = dict(g)
            annotated["_wiki_label"] = wiki_label
            out.append(annotated)
    # Severity sort, take top_n_total.
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda g: (sev_rank.get(g.get("severity", "low"), 9),
                            g.get("type", ""), g.get("id", "")))
    return out[:top_n_total], wikis_seen


def render_page(md_path: Path,
                root: Path,
                output_dir: Path,
                repo_name: str,
                file_count: int,
                *,
                active_section: str | None = None,
                sections_present: list[tuple[str, str]] | None = None,
                section_counts: dict[str, int] | None = None,
                output_root: Path | None = None,
                section_root: Path | None = None,
                gaps_cache: dict[Path, list[dict]] | None = None) -> Path:
    rel = md_path.relative_to(root)
    out_rel = rel.with_suffix(".html")
    out_path = output_dir / out_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md_content = md_path.read_text(encoding="utf-8")
    escaped = html.escape(md_content)

    sidebar_html = render_sidebar(root, output_dir, current_rel=rel, current_html_dir=out_path.parent)
    breadcrumb_html = render_breadcrumb(rel, root, output_dir, current_html_dir=out_path.parent)
    tabs_html = render_tabs(
        active_section=active_section,
        sections_present=sections_present or [],
        section_counts=section_counts or {},
        output_root=output_root or output_dir,
        current_html_dir=out_path.parent,
    )
    action_bar_html = render_action_bar(active_section, rel)

    # Gaps panel: surface on every Wikis-tab page.
    #   - Inside a wiki root (find_wiki_root succeeds) → per-page gaps from
    #     that wiki's GAPS.json.
    #   - On an autogen landing (no GAPS.json walking up) → AGGREGATE gaps
    #     from every wiki under the current dir. Each entry is annotated with
    #     its source wiki so the user can navigate.
    page_gaps: list[dict] = []
    wiki_root_dir: Path | None = None
    is_aggregate = False
    aggregate_count = 0
    if active_section == "wikis" and section_root is not None and gaps_cache is not None:
        wiki_root_dir = find_wiki_root(md_path, section_root)
        if wiki_root_dir is not None:
            page_gaps = gaps_for_page(md_path, section_root, gaps_cache)
        else:
            # Autogen landing — aggregate downward.
            page_dir = md_path.parent
            page_gaps, aggregate_count = aggregate_gaps_under(
                section_root, page_dir, gaps_cache,
            )
            is_aggregate = aggregate_count > 0

    if wiki_root_dir is not None:
        rel_wiki_root = wiki_root_dir.resolve().relative_to(section_root.resolve())
        gaps_html_in_output = output_dir / rel_wiki_root / "GAPS.html"
        gaps_md_href = os.path.relpath(gaps_html_in_output, start=out_path.parent).replace(os.sep, "/")
        gap_count = len(page_gaps)
        gaps_panel_html = (
            '<aside id="gaps-panel">'
            '<h2>Gaps for this page</h2>'
            f'<div class="gp-header-counts">{gap_count} gap(s) referenced — '
            f'see <a href="{html.escape(gaps_md_href)}">GAPS.md</a> for the full report.</div>'
            '<div class="gp-list"></div>'
            '</aside>'
        )
    elif is_aggregate:
        gap_count = len(page_gaps)
        gaps_panel_html = (
            '<aside id="gaps-panel">'
            '<h2>Aggregate gaps</h2>'
            f'<div class="gp-header-counts">{gap_count} gap(s) across '
            f'{aggregate_count} wiki(s) under this branch — drill into a '
            f'specific customer for that wiki\'s full GAPS.md.</div>'
            '<div class="gp-list"></div>'
            '</aside>'
        )
    else:
        gaps_panel_html = ""

    title = f"{rel.as_posix()} — {repo_name}"
    root_index_href = os.path.relpath(output_dir / "index.html", start=out_path.parent).replace(os.sep, "/")

    page_title = extract_h1(md_content, fallback=rel.as_posix())

    page = PAGE_TEMPLATE.format(
        title=html.escape(title),
        repo_name=html.escape(repo_name),
        root_index_href=root_index_href,
        tree_meta=f"{file_count} files",
        sidebar_html=sidebar_html,
        breadcrumb_html=breadcrumb_html,
        source_path=html.escape(rel.as_posix()),
        escaped_md=escaped,
        source_path_json=json.dumps(rel.as_posix()),
        data_path_json=json.dumps(
            f"{active_section}/{rel.as_posix()}" if active_section else rel.as_posix()
        ),
        page_title_json=json.dumps(page_title),
        tabs_html=tabs_html,
        action_bar_html=action_bar_html,
        gaps_panel_html=gaps_panel_html,
        gaps_data_json=html.escape(json.dumps(page_gaps)),
    )
    out_path.write_text(page, encoding="utf-8")
    return out_path


def autogen_section_index(section_root: Path, section_label: str) -> None:
    """Write a section_root/index.md if one is missing.

    Lists immediate subdirs and files as a simple landing page. Idempotent —
    only writes if missing, so user-supplied indexes win.
    """
    idx = section_root / "index.md"
    if idx.exists():
        return
    section_root.mkdir(parents=True, exist_ok=True)
    children = sorted(section_root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    children = [c for c in children if c.name != "index.md"]
    lines = [f"# {section_label}", ""]
    if not children:
        lines.append(f"_No items in {section_label.lower()} yet._")
    else:
        for c in children:
            if c.is_dir() and (c / "index.md").exists():
                lines.append(f"- [{c.name}]({c.name}/index.md)")
            elif c.is_file() and c.suffix == ".md":
                lines.append(f"- [{c.name}]({c.name})")
    lines.append("")
    idx.write_text("\n".join(lines), encoding="utf-8")


def write_top_redirect(output_dir: Path, first_section: str) -> None:
    """Write output_dir/index.html that redirects to the first section's index."""
    target = f"{first_section}/index.html"
    html_doc = (
        "<!DOCTYPE html><html><head>"
        f'<meta http-equiv="refresh" content="0;url={target}">'
        f'<title>Context Center</title></head>'
        f'<body><a href="{target}">{target}</a></body></html>'
    )
    (output_dir / "index.html").write_text(html_doc, encoding="utf-8")


def detect_sections(input_dir: Path) -> list[tuple[str, str]]:
    """Return the subset of recognized sections present under input_dir,
    in the canonical tab order."""
    return [(slug, label) for slug, label in SECTIONS if (input_dir / slug).is_dir()]


def serve(directory: Path, port: int, bind: str = "127.0.0.1") -> None:
    os.chdir(directory)

    class _H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):  # quiet
            pass

    with socketserver.TCPServer((bind, port), _H) as httpd:
        url = f"http://127.0.0.1:{port}/index.html"
        print(f"serving {directory} at {url}", file=sys.stderr)
        if bind != "127.0.0.1":
            print(
                f"  bind={bind} — also reachable from other devices at "
                f"http://<this-host>:{port}/",
                file=sys.stderr,
            )
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.", file=sys.stderr)


def render_section(section_root: Path,
                   section_output: Path,
                   *,
                   section_slug: str,
                   repo_name: str,
                   sections_present: list[tuple[str, str]],
                   section_counts: dict[str, int],
                   output_root: Path) -> int:
    autogen_section_index(section_root, section_label_for(section_slug))
    md_files = collect_md_files(section_root)
    if not md_files:
        # Auto-gen guarantees at least an index.md, so this shouldn't fire.
        return 0
    section_output.mkdir(parents=True, exist_ok=True)
    # Per-section cache so we read each customer's GAPS.json at most once.
    gaps_cache: dict[Path, list[dict]] = {}
    for md in md_files:
        render_page(
            md, section_root, section_output, repo_name=repo_name, file_count=len(md_files),
            active_section=section_slug,
            sections_present=sections_present,
            section_counts=section_counts,
            output_root=output_root,
            section_root=section_root,
            gaps_cache=gaps_cache,
        )
    return len(md_files)


def section_label_for(slug: str) -> str:
    return dict(SECTIONS).get(slug, slug.title())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--repo-name", default="customer-context wiki")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    root = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not root.is_dir():
        sys.exit(f"--input-dir does not exist: {root}")

    output_dir.mkdir(parents=True, exist_ok=True)

    sections_present = detect_sections(root)

    if not sections_present:
        # Single-section / back-compat mode: render the input dir as one tree.
        md_files = collect_md_files(root)
        if not md_files:
            sys.exit(f"no .md files found under {root}")
        for md in md_files:
            render_page(md, root, output_dir, repo_name=args.repo_name, file_count=len(md_files))
        print(f"wrote {len(md_files)} HTML pages to {output_dir}")
        print(f"open: file://{output_dir}/index.html")
    else:
        # Context-center mode: render each detected section into output_dir/<slug>/.
        # Pre-pass: ensure each section has an index, then compute semantic
        # counts. The tab badge counts items (customer wikis / skills /
        # candidates), NOT pages — so it's the number of immediate subdirs
        # under each section root, ignoring the auto-gen index file.
        for slug, _label in sections_present:
            autogen_section_index(root / slug, section_label_for(slug))
        section_counts = {
            slug: sum(1 for c in (root / slug).iterdir() if c.is_dir())
            for slug, _label in sections_present
        }

        total = 0
        for slug, label in sections_present:
            n = render_section(
                root / slug,
                output_dir / slug,
                section_slug=slug,
                repo_name=args.repo_name,
                sections_present=sections_present,
                section_counts=section_counts,
                output_root=output_dir,
            )
            total += n
            print(f"  {label}: wrote {n} pages")

        write_top_redirect(output_dir, sections_present[0][0])
        print(f"wrote {total} HTML pages across {len(sections_present)} section(s) to {output_dir}")
        print(f"open: file://{output_dir}/index.html")

    if args.serve:
        serve(output_dir, args.port)


if __name__ == "__main__":
    main()
